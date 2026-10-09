"""Findings endpoints: retrieve contradictions, run analysis, record reviews."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..models import Finding, FindingReview, FindingStatus, User, UserRole
from ..schemas import FindingOut, FindingReviewRequest
from ..security import get_current_user, require_doctor, require_staff_or_doctor
from ..services import contradiction_service
from ._common import get_visible_patient, serialize_finding

router = APIRouter(prefix="/api", tags=["findings"])


@router.get("/patients/{patient_id}/findings", response_model=list[FindingOut])
def list_patient_findings(
    patient_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    finding_status: FindingStatus | None = Query(default=None),
):
    get_visible_patient(patient_id, user, db)
    query = db.query(Finding).filter(Finding.patient_id == patient_id)
    if finding_status is not None:
        query = query.filter(Finding.status == finding_status)
    findings = query.order_by(Finding.created_at.desc()).all()
    return [serialize_finding(f) for f in findings]


@router.get("/findings/{finding_id}", response_model=FindingOut)
def get_finding(
    finding_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found.")
    get_visible_patient(finding.patient_id, user, db)
    return serialize_finding(finding)


@router.patch("/findings/{finding_id}/review", response_model=FindingOut)
def review_finding(
    finding_id: int,
    payload: FindingReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_doctor),
):
    """A doctor records a review decision (verified/dismissed/escalated) with a reason.

    The review is appended to the finding's history; the finding's status is
    updated and the original medical documents are NEVER modified. Only
    doctors/healthcare professionals may record clinical decisions.
    """
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found.")
    decision = FindingStatus(payload.decision)
    finding.status = decision
    db.add(FindingReview(
        finding_id=finding.id,
        reviewer_user_id=user.id,
        decision=decision,
        reason=payload.reason.strip(),
    ))
    db.commit()
    db.refresh(finding)
    audit.record(db, "finding.review", actor_user_id=user.id, entity_type="finding",
                 entity_id=finding.id, detail=f"decision={decision.value}")
    return serialize_finding(finding)


@router.post("/patients/{patient_id}/analyze", response_model=list[FindingOut])
def run_analysis(
    patient_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_doctor),
):
    """(Re)run the deterministic contradiction rules for a patient.

    Idempotent: existing findings are never duplicated. Output consists of
    POTENTIAL inconsistencies for professional review — not diagnoses.
    """
    get_visible_patient(patient_id, user, db)
    findings = contradiction_service.analyze_patient(db, patient_id)
    audit.record(db, "finding.analyze", actor_user_id=user.id, entity_type="patient",
                 entity_id=patient_id, detail=f"findings={len(findings)}")
    return [serialize_finding(f) for f in findings]
