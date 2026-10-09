"""Shared helpers used by multiple routers."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Finding, Patient, User, UserRole
from ..schemas import FindingOut


def get_visible_patient(patient_id: int, user: User, db: Session) -> Patient:
    """Load a patient enforcing role-based visibility.

    - Patient users: only their own linked patient.
    - Admins: no clinical record access at all.
    - Doctor / records staff: any patient.
    """
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    if user.role == UserRole.patient and user.patient_id != patient.id:
        raise HTTPException(status_code=403, detail="You may only view your own records.")
    if user.role == UserRole.admin:
        raise HTTPException(
            status_code=403,
            detail="Administrators do not have access to clinical patient records.",
        )
    return patient


def serialize_finding(f: Finding) -> FindingOut:
    out = FindingOut.model_validate(f)
    out.source_a_filename = f.document_a.original_filename if f.document_a else None
    out.source_b_filename = f.document_b.original_filename if f.document_b else None
    out.source_a_date = f.document_a.document_date if f.document_a else None
    out.source_b_date = f.document_b.document_date if f.document_b else None
    for src_out, src in zip(out.sources, f.sources):
        src_out.document_filename = src.document.original_filename if src.document else None
    for rev_out, rev in zip(out.reviews, f.reviews):
        rev_out.reviewer_name = rev.reviewer.full_name if rev.reviewer else None
    return out
