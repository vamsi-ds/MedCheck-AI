"""Document endpoints: secure upload, listing, status, metadata correction."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from .. import audit
from ..database import get_db
from ..models import (
    ExtractedText,
    MedicalDocument,
    ProcessingStatus,
    ExtractionStatus,
    User,
    UserRole,
)
from ..schemas import DocumentDetailOut, DocumentMetadataUpdate, DocumentOut, DocumentStatusOut
from ..security import get_current_user, require_staff_or_doctor
from ..services import contradiction_service, document_service
from ._common import get_visible_patient

router = APIRouter(prefix="/api", tags=["documents"])

_DOCUMENT_TYPES = {"consultation", "investigation", "medication", "emergency", "discharge", "other"}


def _doc_out(d: MedicalDocument) -> DocumentOut:
    item = DocumentOut.model_validate(d)
    item.uploaded_by_username = d.uploader.username if d.uploader else None
    return item


@router.get("/patients/{patient_id}/documents", response_model=list[DocumentOut])
def list_documents(
    patient_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_visible_patient(patient_id, user, db)
    docs = (
        db.query(MedicalDocument)
        .filter(MedicalDocument.patient_id == patient_id)
        .order_by(MedicalDocument.uploaded_at.desc())
        .all()
    )
    return [_doc_out(d) for d in docs]


@router.post("/patients/{patient_id}/documents", response_model=DocumentOut,
             status_code=status.HTTP_201_CREATED)
def upload_document(
    patient_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_doctor),
    file: UploadFile = File(...),
    document_type: str = Form(default="other"),
    document_date: str | None = Form(default=None),
):
    """Upload and process a medical document (PDF/PNG/JPG).

    Validates extension, content type, magic bytes, and size; stores a
    server-named copy; extracts text (pypdf, OCR when available); then runs
    the contradiction rules. Extraction failures are reported honestly in the
    document's status — never faked.
    """
    from datetime import date as _date

    patient = get_visible_patient(patient_id, user, db)

    doc_type = (document_type or "other").lower().strip()
    if doc_type not in _DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail=(
            f"Unknown document_type '{document_type}'. "
            f"Allowed: {', '.join(sorted(_DOCUMENT_TYPES))}."
        ))
    doc_date: _date | None = None
    if document_date:
        try:
            doc_date = _date.fromisoformat(document_date)
        except ValueError:
            raise HTTPException(status_code=422, detail="document_date must be ISO format YYYY-MM-DD.")

    data = file.file.read()
    try:
        stored = document_service.validate_and_store(
            filename=file.filename or "", declared_mime=file.content_type or "", data=data
        )
    except document_service.DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    doc = MedicalDocument(
        patient_id=patient.id,
        uploaded_by_user_id=user.id,
        original_filename=(file.filename or "upload")[:255],
        stored_filename=stored.stored_filename,
        document_type=doc_type,
        mime_type=stored.mime_type,
        file_size=stored.size,
        file_sha256=stored.sha256,
        is_synthetic=patient.is_synthetic,
        processing_status=ProcessingStatus.processing,
        document_date=doc_date,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # ---- text extraction (honest statuses) ----
    try:
        text, method = document_service.extract_text(stored.path, stored.mime_type)
        db.add(ExtractedText(
            document_id=doc.id, text=text, method=method, char_count=len(text),
        ))
        doc.extraction_status = ExtractionStatus.succeeded
        doc.processing_status = ProcessingStatus.completed
    except RuntimeError as exc:
        doc.extraction_status = (
            ExtractionStatus.ocr_unavailable
            if "OCR" in str(exc)
            else ExtractionStatus.no_text_found
        )
        doc.processing_status = ProcessingStatus.failed
        doc.extraction_error = str(exc)
    except Exception as exc:  # unexpected extraction failure — record it, never fake success
        doc.extraction_status = ExtractionStatus.failed
        doc.processing_status = ProcessingStatus.failed
        doc.extraction_error = f"Extraction failed: {exc}"
    db.commit()
    db.refresh(doc)

    audit.record(db, "document.upload", actor_user_id=user.id, entity_type="document",
                 entity_id=doc.id,
                 detail=f"patient={patient.id} name={doc.original_filename} "
                        f"extraction={doc.extraction_status.value}")

    # ---- contradiction analysis (only meaningful with extracted text) ----
    if doc.extraction_status == ExtractionStatus.succeeded:
        contradiction_service.analyze_patient(db, patient.id)

    return _doc_out(doc)


@router.get("/documents/{document_id}", response_model=DocumentDetailOut)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.get(MedicalDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    get_visible_patient(doc.patient_id, user, db)
    out = DocumentDetailOut.model_validate(_doc_out(doc))
    if doc.extraction is not None:
        out.extracted_text_preview = doc.extraction.text[:2000]
        out.extracted_char_count = doc.extraction.char_count
        out.extraction_method = doc.extraction.method
    return out


@router.get("/documents/{document_id}/status", response_model=DocumentStatusOut)
def get_document_status(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = db.get(MedicalDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    get_visible_patient(doc.patient_id, user, db)
    return DocumentStatusOut(
        id=doc.id,
        processing_status=doc.processing_status,
        extraction_status=doc.extraction_status,
        extraction_error=doc.extraction_error,
    )


@router.patch("/documents/{document_id}", response_model=DocumentOut)
def update_document_metadata(
    document_id: int,
    payload: DocumentMetadataUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff_or_doctor),
):
    """Records staff may correct document metadata; file content is never altered."""
    doc = db.get(MedicalDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    get_visible_patient(doc.patient_id, user, db)
    data = payload.model_dump(exclude_unset=True)
    if "document_type" in data:
        doc_type = (data["document_type"] or "other").lower().strip()
        if doc_type not in _DOCUMENT_TYPES:
            raise HTTPException(status_code=422, detail=(
                f"Unknown document_type. Allowed: {', '.join(sorted(_DOCUMENT_TYPES))}."
            ))
        doc.document_type = doc_type
    if "document_date" in data:
        doc.document_date = data["document_date"]
    db.commit()
    db.refresh(doc)
    audit.record(db, "document.metadata_update", actor_user_id=user.id, entity_type="document",
                 entity_id=doc.id, detail=f"fields={','.join(data.keys())}")
    return _doc_out(doc)
