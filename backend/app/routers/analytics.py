"""Analytics endpoints: aggregate counts computed from the database."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    Finding,
    FindingStatus,
    MedicalDocument,
    Patient,
    ProcessingStatus,
    User,
    UserStatus,
    Visit,
)
from ..schemas import AnalyticsSummary
from ..security import get_current_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    def count(model, *filters):
        return db.query(func.count(model.id)).filter(*filters).scalar() or 0

    category_rows = (
        db.query(Finding.category, func.count(Finding.id)).group_by(Finding.category).all()
    )
    severity_rows = (
        db.query(Finding.severity, func.count(Finding.id)).group_by(Finding.severity).all()
    )
    return AnalyticsSummary(
        patient_count=count(Patient),
        visit_count=count(Visit),
        document_count=count(MedicalDocument),
        pending_documents=count(MedicalDocument, MedicalDocument.processing_status == ProcessingStatus.pending)
        + count(MedicalDocument, MedicalDocument.processing_status == ProcessingStatus.processing),
        failed_documents=count(MedicalDocument, MedicalDocument.processing_status == ProcessingStatus.failed),
        finding_count=count(Finding),
        findings_needs_review=count(Finding, Finding.status == FindingStatus.needs_review),
        findings_verified=count(Finding, Finding.status == FindingStatus.verified),
        findings_disclaimed=count(Finding, Finding.status == FindingStatus.dismissed),
        findings_escalated=count(Finding, Finding.status == FindingStatus.escalated),
        findings_by_category={cat.value: n for cat, n in category_rows},
        findings_by_severity={sev.value: n for sev, n in severity_rows},
        user_count=count(User),
        pending_users=count(User, User.status == UserStatus.pending),
    )
