"""Pydantic request/response schemas for the MedCheck AI API."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import ExtractionStatus, FindingCategory, FindingStatus, ProcessingStatus, Severity

RoleLiteral = Literal["doctor", "records_staff", "patient", "admin"]


# ---------------------------------------------------------------------- auth

class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=128)
    password: str = Field(min_length=8, max_length=128)
    # Users may request doctor / records_staff / patient. Admin can never be
    # self-assigned; the backend rejects it outright.
    role: Literal["doctor", "records_staff", "patient"]


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str
    role: RoleLiteral
    status: Literal["pending", "active", "inactive"]
    patient_id: int | None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AdminUserUpdate(BaseModel):
    status: Literal["active", "inactive"] | None = None
    role: RoleLiteral | None = None


# ------------------------------------------------------------------ patients

class PatientBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=16)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=80)
    last_name: str | None = Field(default=None, min_length=1, max_length=80)
    date_of_birth: date | None = None
    sex: str | None = Field(default=None, max_length=16)
    phone: str | None = Field(default=None, max_length=32)
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=255)


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mrn: str
    first_name: str
    last_name: str
    full_name: str
    date_of_birth: date | None
    sex: str | None
    phone: str | None
    email: str | None
    address: str | None
    is_synthetic: bool
    created_at: datetime
    open_findings: int = 0
    document_count: int = 0
    visit_count: int = 0


class PatientListOut(BaseModel):
    items: list[PatientOut]
    total: int
    page: int
    page_size: int


# -------------------------------------------------------------------- visits

class VisitCreate(BaseModel):
    visit_date: date
    visit_type: str = Field(min_length=2, max_length=64)
    department: str = Field(min_length=2, max_length=100)
    reason: str = Field(min_length=2, max_length=255)
    purpose: str | None = Field(default=None, max_length=255)
    outcome: str | None = None


class VisitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    visit_date: date
    visit_type: str
    department: str
    reason: str
    purpose: str | None
    outcome: str | None
    created_at: datetime


# ----------------------------------------------------------------- documents

class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    original_filename: str
    document_type: str
    mime_type: str
    file_size: int
    is_synthetic: bool
    processing_status: ProcessingStatus
    extraction_status: ExtractionStatus
    extraction_error: str | None
    uploaded_at: datetime
    document_date: date | None
    uploaded_by_username: str | None = None


class DocumentDetailOut(DocumentOut):
    extracted_text_preview: str | None = None
    extracted_char_count: int | None = None
    extraction_method: str | None = None


class DocumentStatusOut(BaseModel):
    id: int
    processing_status: ProcessingStatus
    extraction_status: ExtractionStatus
    extraction_error: str | None


class DocumentMetadataUpdate(BaseModel):
    document_type: str | None = Field(default=None, max_length=64)
    document_date: date | None = None


# ------------------------------------------------------------------ findings

class FindingSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    excerpt: str
    match_reason: str
    document_date: date | None
    document_filename: str | None = None


class FindingReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reviewer_user_id: int
    reviewer_name: str | None = None
    decision: FindingStatus
    reason: str
    created_at: datetime


class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    category: FindingCategory
    severity: Severity
    title: str
    description: str
    explanation: str
    status: FindingStatus
    rule_key: str
    confidence: float
    source_a_document_id: int
    source_b_document_id: int
    source_a_filename: str | None = None
    source_b_filename: str | None = None
    source_a_date: date | None = None
    source_b_date: date | None = None
    created_at: datetime
    updated_at: datetime
    sources: list[FindingSourceOut] = []
    reviews: list[FindingReviewOut] = []


class FindingReviewRequest(BaseModel):
    # A reviewer records a decision with a mandatory reason. Original medical
    # documents are never modified by a review.
    decision: Literal["verified", "dismissed", "escalated"]
    reason: str = Field(min_length=5, max_length=1000)


# ----------------------------------------------------------------- analytics

class AnalyticsSummary(BaseModel):
    patient_count: int
    visit_count: int
    document_count: int
    pending_documents: int
    failed_documents: int
    finding_count: int
    findings_needs_review: int
    findings_verified: int
    findings_disclaimed: int  # dismissed
    findings_escalated: int
    findings_by_category: dict[str, int]
    findings_by_severity: dict[str, int]
    user_count: int
    pending_users: int


# ----------------------------------------------------------------- correction

class CorrectionRequestCreate(BaseModel):
    message: str = Field(min_length=10, max_length=1000)


class CorrectionRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    message: str
    status: str
    created_at: datetime


# --------------------------------------------------------------------- audit

class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    actor_username: str | None = None
    action: str
    entity_type: str | None
    entity_id: str | None
    detail: str | None
    created_at: datetime


# -------------------------------------------------------------------- health

class HealthOut(BaseModel):
    status: Literal["ok"]
    database: Literal["connected"]
    ocr_available: bool
    version: str
