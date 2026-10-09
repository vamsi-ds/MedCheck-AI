"""Visit endpoints: chronological patient visit history."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..models import Patient, User, Visit
from ..schemas import VisitCreate, VisitOut
from ..security import get_current_user, require_staff_or_doctor
from ._common import get_visible_patient

router = APIRouter(prefix="/api/patients/{patient_id}/visits", tags=["visits"])


@router.get("", response_model=list[VisitOut])
def list_visits(
    patient_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_visible_patient(patient_id, user, db)
    return (
        db.query(Visit)
        .filter(Visit.patient_id == patient_id)
        .order_by(Visit.visit_date)
        .all()
    )


@router.post("", response_model=VisitOut, status_code=status.HTTP_201_CREATED)
def create_visit(
    patient_id: int,
    payload: VisitCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_doctor),
):
    get_visible_patient(patient_id, user, db)
    visit = Visit(patient_id=patient_id, **payload.model_dump())
    db.add(visit)
    db.commit()
    db.refresh(visit)
    audit.record(db, "visit.create", actor_user_id=user.id, entity_type="visit",
                 entity_id=visit.id, detail=f"patient={patient_id}")
    return visit
