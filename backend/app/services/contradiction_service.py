"""Explainable, deterministic contradiction detection over extracted document text.

Design principles (deliberate, documented):
- RULE-BASED and deterministic. No external AI services are called. Every
  finding records which rule fired, the matched excerpts, and why they matched,
  so a human reviewer can trace it end to end.
- Absence of a statement is NEVER treated as evidence of falsehood. We only
  flag documents that make explicit, opposing assertions.
- Negation is handled explicitly ("no known drug allergies" vs "allergic to X").
- The newest document is not assumed correct; both sides are presented with
  their dates and the reviewer decides.
- All outputs are worded as POTENTIAL inconsistencies requiring verification by
  a qualified professional. Nothing here diagnoses or changes records.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..models import (
    ExtractedText,
    Finding,
    FindingCategory,
    FindingSource,
    FindingStatus,
    MedicalDocument,
    Severity,
)

DISCLAIMER = (
    "This is an algorithmic comparison of extracted document text and a "
    "potential inconsistency only. It must be verified against the original "
    "documents by a qualified healthcare professional."
)

# ---------------------------------------------------------------- rule data

ALLERGY_NEGATION_RE = re.compile(
    r"no\s+(known\s+)?(drug\s+)?allerg(y|ies)|\bNKDA\b", re.IGNORECASE
)
ALLERGY_POSITIVE_RE = re.compile(
    r"(?:allerg(?:y|ic)\s+(?:to)|known\s+allerg(?:y|ies)\s*:?\s*)([A-Za-z][A-Za-z\s-]{2,40})",
    re.IGNORECASE,
)
# Also matches "penicillin allergy with hives" (allergen precedes the word allergy).
ALLERGY_NAMED_RE = re.compile(
    r"\b([A-Z][a-z]+|[a-z]{4,})\s+allerg(?:y|ic|ies)\b", re.IGNORECASE
)
ALLERGY_STOPWORDS = {"no", "known", "drug", "all", "any", "nkda", "negative", "none"}

MEDICATION_RE = re.compile(
    r"\b([A-Z][a-z]+(?:in|ol|ole|um|am|ptin|mycin|cillin|olol|azepam|pine|statin))\b"
    r"\s+(\d+\s?(?:mg|mcg|g|ml))\b",
    re.IGNORECASE,
)
MED_STOPPED_RE = re.compile(
    r"(?:stopped|discontinued|ceased|cancelled|no longer)\s+([A-Za-z][A-Za-z-]{2,30})"
    r"|([A-Za-z][A-Za-z-]{2,30})\s+(?:was\s+)?(?:stopped|discontinued|ceased|cancelled)",
    re.IGNORECASE,
)
MED_ACTIVE_RE = re.compile(
    r"(?:continue[sd]?|started|commenced|resume[sd]?|currently\s+taking)\s+([A-Za-z][A-Za-z-]{2,30})"
    r"|([A-Za-z][A-Za-z-]{2,30})\s+(?:was\s+)?(?:continued|restarted|resumed|started)",
    re.IGNORECASE,
)

DIAGNOSIS_ACTIVE_RE = re.compile(
    r"([A-Za-z][A-Za-z -]{3,40}?)\s*(?:is\s+)?(?:active|ongoing|uncontrolled|acute)", re.IGNORECASE
)
DIAGNOSIS_RESOLVED_RE = re.compile(
    r"([A-Za-z][A-Za-z -]{3,40}?)\s*(?:is\s+)?(?:resolved|inactive|controlled|in remission)",
    re.IGNORECASE,
)

DOB_RE = re.compile(
    r"(?:date\s+of\s+birth|dob|born(?:\s+on)?)\s*[:\-]?\s*"
    r"(\d{1,2}[ /.\-](?:\d{1,2}|[A-Za-z]+)[ /.\-]\d{4}|\d{4}[ /.\-]\d{1,2}[ /.\-]\d{1,2})",
    re.IGNORECASE,
)

KNOWN_CONDITIONS = [
    "hypertension", "type 2 diabetes", "diabetes", "asthma", "copd",
    "atrial fibrillation", "heart failure", "pneumonia", "migraine",
    "osteoarthritis", "depression", "hypothyroidism",
]

# ------------------------------------------------------------------ helpers

def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p and p.strip()]


def _excerpt_around(sentence: str, limit: int = 240) -> str:
    s = re.sub(r"\s+", " ", sentence).strip()
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


@dataclass
class CandidateMatch:
    rule_key: str
    category: FindingCategory
    severity: Severity
    confidence: float
    title: str
    description: str
    explanation: str
    excerpt_a: str
    excerpt_b: str
    reason_a: str
    reason_b: str


@dataclass
class DocInfo:
    doc: MedicalDocument
    text: str
    sentences: list[str] = field(default_factory=list)


# -------------------------------------------------------------------- rules

def _extract_allergen_name(sentence: str) -> str:
    """Best-effort allergen name from a sentence; defaults to a generic label."""
    m = ALLERGY_POSITIVE_RE.search(sentence)
    if m:
        return m.group(1).strip().title()
    # For "X allergy" phrasing, take the last non-stopword candidate
    # (handles sentences like "Advised allergy wristband noting penicillin allergy.").
    candidates = [
        c.group(1) for c in ALLERGY_NAMED_RE.finditer(sentence)
        if c.group(1).lower() not in ALLERGY_STOPWORDS
    ]
    if candidates:
        return candidates[-1].strip().title()
    return "an allergen"


def _find_allergy_sentence(doc: DocInfo) -> str | None:
    """Return a sentence asserting a NAMED allergy (not a negation statement)."""
    for s in doc.sentences:
        if ALLERGY_NEGATION_RE.search(s):
            continue
        m = ALLERGY_POSITIVE_RE.search(s)
        if m:
            return s
        m = ALLERGY_NAMED_RE.search(s)
        if m and m.group(1).lower() not in ALLERGY_STOPWORDS:
            return s
    return None


def _rule_allergy(a: DocInfo, b: DocInfo) -> CandidateMatch | None:
    """Explicit 'no known allergies' in one document vs a named allergy in another."""
    a_neg = next((s for s in a.sentences if ALLERGY_NEGATION_RE.search(s)), None)
    b_neg = next((s for s in b.sentences if ALLERGY_NEGATION_RE.search(s)), None)
    a_pos = _find_allergy_sentence(a)
    b_pos = _find_allergy_sentence(b)

    if a_neg and b_pos:
        neg, pos, neg_doc, pos_doc = a_neg, b_pos, a, b
    elif b_neg and a_pos:
        neg, pos, neg_doc, pos_doc = b_neg, a_pos, b, a
    else:
        return None

    drug_name = _extract_allergen_name(pos)
    return CandidateMatch(
        rule_key="allergy.negation_vs_named",
        category=FindingCategory.allergy,
        severity=Severity.high,
        confidence=0.85,
        title=f"Allergy status conflicts: {drug_name}",
        description=(
            f"One record states there are no known allergies, while another record "
            f"lists {drug_name} as an allergy. This is a potential inconsistency "
            f"requiring professional verification."
        ),
        explanation=(
            f"Rule 'allergy.negation_vs_named' matched: '{neg_doc.doc.original_filename}' "
            f"contains an explicit no-known-allergies statement, and "
            f"'{pos_doc.doc.original_filename}' names a specific allergy. Both excerpts "
            f"are explicit assertions, so both are presented without assuming either is correct."
        ),
        excerpt_a=_excerpt_around(neg),
        excerpt_b=_excerpt_around(pos),
        reason_a="Explicit 'no known allergies' statement",
        reason_b=f"Named allergy: {drug_name}",
    )


def _med_map(doc: DocInfo) -> dict[str, list[tuple[str, str]]]:
    """Map lowercased drug name -> list of (dose_or_status, sentence)."""
    non_drug = {
        "after", "before", "daily", "night", "morning", "evening", "once", "twice",
        "pending", "review", "the", "and", "with", "was", "is", "at", "on", "in",
        "to", "for", "mg", "patient", "report", "reports", "hours", "days", "weeks",
    }
    found: dict[str, list[tuple[str, str]]] = {}
    for s in doc.sentences:
        for m in MEDICATION_RE.finditer(s):
            found.setdefault(m.group(1).lower(), []).append((m.group(2).lower().replace(" ", ""), s))
        for m in MED_STOPPED_RE.finditer(s):
            name = (m.group(1) or m.group(2) or "").lower()
            if name and name not in non_drug:
                found.setdefault(name, []).append(("stopped", s))
        for m in MED_ACTIVE_RE.finditer(s):
            name = (m.group(1) or m.group(2) or "").lower()
            if name and name not in non_drug:
                found.setdefault(name, []).append(("active", s))
    return found


def _rule_medication(a: DocInfo, b: DocInfo) -> list[CandidateMatch]:
    """Same medication with a different dose, or active vs stopped."""
    out: list[CandidateMatch] = []
    map_a, map_b = _med_map(a), _med_map(b)
    for drug in sorted(set(map_a) & set(map_b)):
        doses_a = {v for v, _ in map_a[drug]}
        doses_b = {v for v, _ in map_b[drug]}
        drug_label = drug.title()
        if "stopped" in doses_a and ("active" in doses_b or any(d not in ("stopped",) for d in doses_b - {"stopped"})):
            s_a = next(s for v, s in map_a[drug] if v == "stopped")
            s_b = next(s for v, s in map_b[drug] if v != "stopped")
            out.append(CandidateMatch(
                rule_key="medication.stopped_vs_active",
                category=FindingCategory.medication,
                severity=Severity.high,
                confidence=0.8,
                title=f"{drug_label} medication status differs",
                description=(
                    f"{drug_label} is described as stopped in one record and active in "
                    f"another. Verify dates and source documents; this is a potential "
                    f"inconsistency, not a confirmed error."
                ),
                explanation=(
                    f"Rule 'medication.stopped_vs_active': explicit stop/cancel statement "
                    f"in one document vs explicit continue/start statement in another for "
                    f"{drug_label}."
                ),
                excerpt_a=_excerpt_around(s_a),
                excerpt_b=_excerpt_around(s_b),
                reason_a="Stop/cancel statement",
                reason_b="Continue/start statement",
            ))
        elif any(d.endswith(("mg", "mcg", "g", "ml")) for d in doses_a) and any(
            d.endswith(("mg", "mcg", "g", "ml")) for d in doses_b
        ):
            numeric_a = {d for d in doses_a if any(c.isdigit() for c in d)}
            numeric_b = {d for d in doses_b if any(c.isdigit() for c in d)}
            if numeric_a and numeric_b and not (numeric_a & numeric_b):
                s_a = next(s for v, s in map_a[drug] if v in numeric_a)
                s_b = next(s for v, s in map_b[drug] if v in numeric_b)
                out.append(CandidateMatch(
                    rule_key="medication.dose_mismatch",
                    category=FindingCategory.medication,
                    severity=Severity.medium,
                    confidence=0.75,
                    title=f"{drug_label} dose differs between records",
                    description=(
                        f"The recorded dose of {drug_label} differs between two documents "
                        f"({', '.join(sorted(numeric_a))} vs {', '.join(sorted(numeric_b))}). "
                        f"A dose change may be intentional — verify against the source "
                        f"documents and dates."
                    ),
                    explanation=(
                        f"Rule 'medication.dose_mismatch': numeric doses for {drug_label} "
                        f"found in both documents that do not match."
                    ),
                    excerpt_a=_excerpt_around(s_a),
                    excerpt_b=_excerpt_around(s_b),
                    reason_a=f"Recorded dose: {', '.join(sorted(numeric_a))}",
                    reason_b=f"Recorded dose: {', '.join(sorted(numeric_b))}",
                ))
    return out


def _norm_condition(raw: str) -> str | None:
    raw_l = raw.lower().strip(" ,.;:")
    for cond in KNOWN_CONDITIONS:
        if cond in raw_l:
            return cond
    return None


def _rule_diagnosis(a: DocInfo, b: DocInfo) -> list[CandidateMatch]:
    """Same condition described as active/acute in one record and resolved/controlled in another."""
    out: list[CandidateMatch] = []

    def active(doc: DocInfo) -> dict[str, str]:
        res: dict[str, str] = {}
        for s in doc.sentences:
            for m in DIAGNOSIS_ACTIVE_RE.finditer(s):
                cond = _norm_condition(m.group(1))
                if cond:
                    res.setdefault(cond, s)
        return res

    def resolved(doc: DocInfo) -> dict[str, str]:
        res: dict[str, str] = {}
        for s in doc.sentences:
            for m in DIAGNOSIS_RESOLVED_RE.finditer(s):
                cond = _norm_condition(m.group(1))
                if cond:
                    res.setdefault(cond, s)
        return res

    for cond in sorted(set(active(a)) & set(resolved(b))):
        out.append(_diag_match(cond, active(a)[cond], resolved(b)[cond], "a_active"))
    for cond in sorted(set(active(b)) & set(resolved(a))):
        out.append(_diag_match(cond, active(b)[cond], resolved(a)[cond], "b_active"))
    return out


def _diag_match(cond: str, active_sentence: str, resolved_sentence: str, side: str) -> CandidateMatch:
    label = cond.title()
    return CandidateMatch(
        rule_key="diagnosis.status_mismatch",
        category=FindingCategory.diagnosis,
        severity=Severity.medium,
        confidence=0.7,
        title=f"{label} recorded with differing status",
        description=(
            f"{label} is described as active/uncontrolled in one record and "
            f"resolved/controlled in another. Conditions can legitimately change over "
            f"time — verify the dates of both documents."
        ),
        explanation=(
            f"Rule 'diagnosis.status_mismatch': the same condition appears with an "
            f"active-status phrase in one document and a resolved-status phrase in another."
        ),
        excerpt_a=_excerpt_around(active_sentence),
        excerpt_b=_excerpt_around(resolved_sentence),
        reason_a="Active-status wording",
        reason_b="Resolved-status wording",
    )


def _parse_dob(s: str):
    """Return a comparable YYYY-MM-DD string, or the raw normalized string."""
    s = s.strip().replace(".", "/").replace("-", "/").replace(" ", "/")
    parts = [p for p in s.split("/") if p]
    try:
        if len(parts) == 3:
            if len(parts[0]) == 4:  # YYYY/M/D
                return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
            return f"{int(parts[2]):04d}-{int(parts[1]):02d}-{int(parts[0]):02d}"  # D/M/Y
    except ValueError:
        return None
    return None


def _rule_demographic(a: DocInfo, b: DocInfo) -> list[CandidateMatch]:
    """Conflicting explicit date-of-birth statements across documents."""
    out: list[CandidateMatch] = []
    dob_a = next((m.group(1) for s in a.sentences for m in [DOB_RE.search(s)] if m), None)
    dob_b = next((m.group(1) for s in b.sentences for m in [DOB_RE.search(s)] if m), None)
    if not dob_a or not dob_b:
        return out  # missing information is not evidence of a conflict
    parsed_a, parsed_b = _parse_dob(dob_a), _parse_dob(dob_b)
    if parsed_a and parsed_b and parsed_a != parsed_b:
        s_a = next(s for s in a.sentences if DOB_RE.search(s))
        s_b = next(s for s in b.sentences if DOB_RE.search(s))
        out.append(CandidateMatch(
            rule_key="demographic.dob_mismatch",
            category=FindingCategory.demographic,
            severity=Severity.high,
            confidence=0.9,
            title="Date of birth differs between records",
            description=(
                f"The two documents state different dates of birth "
                f"({parsed_a} vs {parsed_b}). Verify patient identity against the "
                f"original records."
            ),
            explanation=(
                "Rule 'demographic.dob_mismatch': both documents contain an explicit "
                "date-of-birth statement and the parsed dates differ."
            ),
            excerpt_a=_excerpt_around(s_a),
            excerpt_b=_excerpt_around(s_b),
            reason_a=f"Stated date of birth: {parsed_a}",
            reason_b=f"Stated date of birth: {parsed_b}",
        ))
    return out


_SINGLE_MATCH_RULES = [
    _rule_allergy,
]

_LIST_RULES = [
    _rule_medication,
    _rule_diagnosis,
    _rule_demographic,
]


# ----------------------------------------------------------------- pipeline

def analyze_patient(db: Session, patient_id: int) -> list[Finding]:
    """Run all rules over every pair of documents with extracted text.

    Idempotent: findings are deduplicated by (patient, rule, document pair).
    Returns the full list of findings for the patient afterwards.
    """
    docs = (
        db.query(MedicalDocument, ExtractedText)
        .join(ExtractedText, ExtractedText.document_id == MedicalDocument.id)
        .filter(MedicalDocument.patient_id == patient_id)
        .all()
    )
    infos = [
        DocInfo(doc=doc, text=ext.text, sentences=_sentences(ext.text))
        for doc, ext in docs
    ]

    candidates: list[tuple[CandidateMatch, DocInfo, DocInfo]] = []
    for i in range(len(infos)):
        for j in range(i + 1, len(infos)):
            a, b = infos[i], infos[j]
            for rule in _SINGLE_MATCH_RULES:
                result = rule(a, b)
                if result is not None:
                    candidates.append((result, a, b))
            for rule in _LIST_RULES:
                for match in rule(a, b):
                    candidates.append((match, a, b))

    for match, a, b in candidates:
        existing = (
            db.query(Finding)
            .filter(
                Finding.patient_id == patient_id,
                Finding.rule_key == match.rule_key,
                Finding.source_a_document_id == a.doc.id,
                Finding.source_b_document_id == b.doc.id,
            )
            .first()
        )
        if existing is not None:
            continue
        finding = Finding(
            patient_id=patient_id,
            category=match.category,
            severity=match.severity,
            title=match.title,
            description=match.description,
            explanation=match.explanation,
            status=FindingStatus.needs_review,
            rule_key=match.rule_key,
            confidence=match.confidence,
            source_a_document_id=a.doc.id,
            source_b_document_id=b.doc.id,
        )
        db.add(finding)
        db.flush()  # assign finding.id
        db.add(FindingSource(
            finding_id=finding.id,
            document_id=a.doc.id,
            excerpt=match.excerpt_a,
            match_reason=match.reason_a,
            document_date=a.doc.document_date,
        ))
        db.add(FindingSource(
            finding_id=finding.id,
            document_id=b.doc.id,
            excerpt=match.excerpt_b,
            match_reason=match.reason_b,
            document_date=b.doc.document_date,
        ))
    db.commit()

    return (
        db.query(Finding)
        .filter(Finding.patient_id == patient_id)
        .order_by(Finding.created_at.desc())
        .all()
    )
