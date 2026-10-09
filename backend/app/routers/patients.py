"""Patient endpoints: directory, profiles, correction requests.

Access control:
- Doctor / Records staff: full directory access.
- Patient users: only the single patient record linked to their account.
- Admin: no clinical access (administrators manage accounts and audit, not care).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..models import (
    Finding,
    FindingStatus,
    MedicalDocument,
    Patient,
    User,
    UserRole,
    Visit,
)
from ..schemas import (
    CorrectionRequestCreate,
    PatientCreate,
    PatientListOut,
    PatientOut,
    PatientUpdate,
)
from ..security import get_current_user, require_staff_or_doctor
from ._common import get_visible_patient

router = APIRouter(prefix="/api/patients", tags=["patients"])


def _enrich_patient(patient: Patient, db: Session) -> PatientOut:
    out = PatientOut.model_validate(patient)
    out.open_findings = (
        db.query(func.count(Finding.id))
        .filter(Finding.patient_id == patient.id, Finding.status == FindingStatus.needs_review)
        .scalar() or 0
    )
    out.document_count = (
        db.query(func.count(MedicalDocument.id))
        .filter(MedicalDocument.patient_id == patient.id).scalar() or 0
    )
    out.visit_count = db.query(func.count(Visit.id)).filter(Visit.patient_id == patient.id).scalar() or 0
    return out


def _visible_patients_query(user: User, db: Session):
    q = db.query(Patient)
    if user.role == UserRole.patient:
        if user.patient_id is None:
            return q.filter(Patient.id == -1)  # empty result
        q = q.filter(Patient.id == user.patient_id)
    return q


@router.get("", response_model=PatientListOut)
def list_patients(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    if user.role == UserRole.admin:
        raise HTTPException(
            status_code=403,
            detail="Administrators do not have access to clinical patient records.",
        )
    query = _visible_patients_query(user, db)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(Patient.mrn.ilike(like), Patient.first_name.ilike(like),
                                 Patient.last_name.ilike(like)))
    total = query.count()
    patients = (
        query.order_by(Patient.mrn)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PatientListOut(
        items=[_enrich_patient(p, db) for p in patients],
        total=total, page=page, page_size=page_size,
    )


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_doctor),
):
    """Register a new synthetic patient record."""
    prefix_count = db.query(func.count(Patient.id)).scalar() or 0
    patient = Patient(
        mrn=f"MC-{prefix_count + 1:03d}",
        first_name=payload.first_name,
        last_name=payload.last_name,
        date_of_birth=payload.date_of_birth,
        sex=payload.sex,
        phone=payload.phone,
        email=payload.email,
        address=payload.address,
        is_synthetic=True,
        created_by_user_id=user.id,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    audit.record(db, "patient.create", actor_user_id=user.id, entity_type="patient",
                 entity_id=patient.id, detail=f"mrn={patient.mrn}")
    return _enrich_patient(patient, db)


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _enrich_patient(get_visible_patient(patient_id, user, db), db)


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_doctor),
):
    """Correct patient demographics/metadata; original documents are untouched."""
    patient = get_visible_patient(patient_id, user, db)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(patient, key, value)
    db.commit()
    db.refresh(patient)
    audit.record(db, "patient.update", actor_user_id=user.id, entity_type="patient",
                 entity_id=patient.id, detail=f"fields={','.join(data.keys())}")
    return _enrich_patient(patient, db)


@router.post("/{patient_id}/correction-requests", status_code=status.HTTP_201_CREATED)
def request_correction(
    patient_id: int,
    payload: CorrectionRequestCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Record a correction request against a patient record (audit-logged)."""
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    if user.role == UserRole.patient and user.patient_id != patient_id:
        raise HTTPException(status_code=403, detail="You may only request corrections for your own record.")
    if user.role not in (UserRole.patient, UserRole.doctor, UserRole.records_staff):
        raise HTTPException(status_code=403, detail="Your role cannot submit correction requests.")
    audit.record(db, "correction.request", actor_user_id=user.id, entity_type="patient",
                 entity_id=patient_id, detail=payload.message[:500])
    return Response(status_code=status.HTTP_201_CREATED)
