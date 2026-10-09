"""SQLAlchemy ORM models for MedCheck AI.

Entities: users, patients, visits, documents, extracted text, findings,
finding sources (evidence), finding reviews, audit events.
All data handled by this system must be synthetic/demo data.
"""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    doctor = "doctor"
    records_staff = "records_staff"
    patient = "patient"
    admin = "admin"


class UserStatus(str, enum.Enum):
    pending = "pending"  # registered, awaiting administrator approval
    active = "active"
    inactive = "inactive"


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ExtractionStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    no_text_found = "no_text_found"  # needs OCR
    ocr_unavailable = "ocr_unavailable"
    failed = "failed"


class FindingStatus(str, enum.Enum):
    needs_review = "needs_review"
    verified = "verified"
    dismissed = "dismissed"
    escalated = "escalated"


class FindingCategory(str, enum.Enum):
    allergy = "allergy"
    medication = "medication"
    diagnosis = "diagnosis"
    demographic = "demographic"


class Severity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    # PBKDF2-SHA256 hash: "pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>"
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), index=True)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.pending, index=True)
    # For user accounts that belong to a registered patient (patient role).
    patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    patient: Mapped[Patient | None] = relationship(
        "Patient", back_populates="linked_user", foreign_keys=[patient_id]
    )


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mrn: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # e.g. MC-001
    first_name: Mapped[str] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(16), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    visits: Mapped[list[Visit]] = relationship(
        "Visit", back_populates="patient", cascade="all, delete-orphan", order_by="Visit.visit_date"
    )
    documents: Mapped[list[MedicalDocument]] = relationship(
        "MedicalDocument", back_populates="patient", cascade="all, delete-orphan"
    )
    findings: Mapped[list[Finding]] = relationship(
        "Finding", back_populates="patient", cascade="all, delete-orphan"
    )
    linked_user: Mapped[User | None] = relationship(
        "User", back_populates="patient", uselist=False, foreign_keys=[User.patient_id]
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    visit_date: Mapped[date] = mapped_column(Date)
    visit_type: Mapped[str] = mapped_column(String(64))  # Consultation, Investigation, ...
    department: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    patient: Mapped[Patient] = relationship("Patient", back_populates="visits")


class MedicalDocument(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    uploaded_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)  # server-generated
    document_type: Mapped[str] = mapped_column(String(64), default="other")
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size: Mapped[int] = mapped_column(Integer)
    file_sha256: Mapped[str] = mapped_column(String(64))
    # If True the stored file is a synthetic seed file created by the backend
    # (still a real file on disk, generated deterministically).
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus), default=ProcessingStatus.pending
    )
    extraction_status: Mapped[ExtractionStatus] = mapped_column(
        Enum(ExtractionStatus), default=ExtractionStatus.pending
    )
    extraction_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    patient: Mapped[Patient] = relationship("Patient", back_populates="documents")
    extraction: Mapped[ExtractedText | None] = relationship(
        "ExtractedText", back_populates="document", uselist=False, cascade="all, delete-orphan"
    )
    uploader: Mapped[User | None] = relationship("User")


class ExtractedText(Base):
    __tablename__ = "extracted_text"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), unique=True, index=True
    )
    text: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(32))  # "pdf_text" | "ocr" | "seed"
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[MedicalDocument] = relationship("MedicalDocument", back_populates="extraction")


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        # One finding per (patient, rule, document pair) — keeps re-analysis idempotent.
        UniqueConstraint("patient_id", "rule_key", "source_a_document_id", "source_b_document_id",
                         name="uq_finding_dedup"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    category: Mapped[FindingCategory] = mapped_column(Enum(FindingCategory), index=True)
    severity: Mapped[Severity] = mapped_column(Enum(Severity), default=Severity.medium)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)  # plain-language explanation
    explanation: Mapped[str] = mapped_column(Text)  # why the rule fired
    status: Mapped[FindingStatus] = mapped_column(Enum(FindingStatus), default=FindingStatus.needs_review, index=True)
    rule_key: Mapped[str] = mapped_column(String(80))  # deterministic rule id
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    source_a_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    source_b_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    patient: Mapped[Patient] = relationship("Patient", back_populates="findings")
    document_a: Mapped[MedicalDocument] = relationship("MedicalDocument", foreign_keys=[source_a_document_id])
    document_b: Mapped[MedicalDocument] = relationship("MedicalDocument", foreign_keys=[source_b_document_id])
    sources: Mapped[list[FindingSource]] = relationship(
        "FindingSource", back_populates="finding", cascade="all, delete-orphan"
    )
    reviews: Mapped[list[FindingReview]] = relationship(
        "FindingReview", back_populates="finding", cascade="all, delete-orphan", order_by="FindingReview.created_at"
    )


class FindingSource(Base):
    """Evidence excerpt pointing at a location inside a source document."""

    __tablename__ = "finding_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    excerpt: Mapped[str] = mapped_column(Text)  # short evidence excerpt
    match_reason: Mapped[str] = mapped_column(String(255))  # why this excerpt matched
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    finding: Mapped[Finding] = relationship("Finding", back_populates="sources")
    document: Mapped[MedicalDocument] = relationship("MedicalDocument")


class FindingReview(Base):
    __tablename__ = "finding_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    reviewer_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[FindingStatus] = mapped_column(Enum(FindingStatus))  # verified/dismissed/escalated
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    finding: Mapped[Finding] = relationship("Finding", back_populates="reviews")
    reviewer: Mapped[User] = relationship("User")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)  # e.g. "user.login", "finding.review"
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    actor: Mapped[User | None] = relationship("User")
