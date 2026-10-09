"""Contradiction-detection unit tests on synthetic examples.

These test the rule engine directly with synthetic text — no external AI.
"""
from app.services.contradiction_service import (
    CandidateMatch,
    DocInfo,
    _rule_allergy,
    _rule_demographic,
    _rule_diagnosis,
    _rule_medication,
)
from app.models import MedicalDocument


def _doc(filename: str, text: str, day: int = 1) -> DocInfo:
    fake = MedicalDocument(original_filename=filename, stored_filename=filename,
                           mime_type="application/pdf", file_size=1, file_sha256="x" * 64)
    from app.services.contradiction_service import _sentences
    return DocInfo(doc=fake, text=text, sentences=_sentences(text))


def test_allergy_negation_vs_named():
    a = _doc("a.pdf", "Allergies: No known drug allergies.")
    b = _doc("b.pdf", "Known allergy to Penicillin with hives.")
    match = _rule_allergy(a, b)
    assert isinstance(match, CandidateMatch)
    assert match.category.value == "allergy"
    assert "penicillin" in match.title.lower()
    assert match.excerpt_a and match.excerpt_b
    assert "potential" in match.description.lower()


def test_allergy_absence_is_not_a_conflict():
    """A document that says nothing about allergies must NOT create a finding."""
    a = _doc("a.pdf", "Patient reports headache. Vitals stable.")
    b = _doc("b.pdf", "Known allergy to Penicillin with hives.")
    assert _rule_allergy(a, b) is None


def test_allergy_both_positive_no_conflict():
    a = _doc("a.pdf", "Allergy to Penicillin documented.")
    b = _doc("b.pdf", "Known allergy to Penicillin continues.")
    assert _rule_allergy(a, b) is None


def test_medication_dose_mismatch():
    a = _doc("a.pdf", "Continue Metformin 500 mg twice daily.")
    b = _doc("b.pdf", "Metformin 1000 mg once daily restarted after review.")
    matches = _rule_medication(a, b)
    assert any(m.rule_key == "medication.dose_mismatch" for m in matches)


def test_medication_stopped_vs_active():
    a = _doc("a.pdf", "Metformin stopped pending review.")
    b = _doc("b.pdf", "Continue Metformin 500 mg twice daily.")
    matches = _rule_medication(a, b)
    assert any(m.rule_key == "medication.stopped_vs_active" for m in matches)


def test_diagnosis_status_mismatch():
    a = _doc("a.pdf", "Hypertension is active and monitored.")
    b = _doc("b.pdf", "Hypertension is controlled on current regimen.")
    matches = _rule_diagnosis(a, b)
    assert any(m.rule_key == "diagnosis.status_mismatch" for m in matches)


def test_dob_mismatch():
    a = _doc("a.pdf", "Date of birth: 4/3/1991. Seen for headache.")
    b = _doc("b.pdf", "DOB: 5/3/1991. Emergency admission.")
    matches = _rule_demographic(a, b)
    assert any(m.rule_key == "demographic.dob_mismatch" for m in matches)


def test_dob_missing_is_not_a_conflict():
    a = _doc("a.pdf", "Date of birth: 4/3/1991. Seen for headache.")
    b = _doc("b.pdf", "Seen for dizziness. Vitals stable.")
    assert _rule_demographic(a, b) == []


def test_dob_matching_is_not_a_conflict():
    a = _doc("a.pdf", "Date of birth: 4/3/1991. Seen for headache.")
    b = _doc("b.pdf", "DOB: 4/3/1991. Emergency admission.")
    assert _rule_demographic(a, b) == []
