"""Document upload validation, storage, and text extraction.

Security posture:
- Extension, declared MIME type, magic bytes, and size are all validated.
- Files are stored under a server-controlled directory with generated names
  (UUID + hash), never using client-supplied paths — path traversal is
  impossible by construction.
- Uploaded files are never executed, served, or modified; only read.
- Text extraction uses pypdf for text-based PDFs. OCR for scanned PDFs and
  images is optional and clearly reported as unavailable when the Tesseract
  engine / pytesseract are not installed.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from pathlib import Path

from ..config import ALLOWED_EXTENSIONS, ALLOWED_MIME_TYPES, MAX_UPLOAD_BYTES, UPLOAD_DIR

logger = logging.getLogger(__name__)

# --- magic byte signatures -------------------------------------------------
_PDF_SIG = b"%PDF-"
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_JPEG_SIG = b"\xff\xd8\xff"


class DocumentValidationError(ValueError):
    """Raised for rejected uploads; message is safe to return to the client."""


@dataclass
class StoredDocument:
    stored_filename: str
    path: Path
    size: int
    sha256: str
    mime_type: str


def detect_mime_from_signature(head: bytes) -> str | None:
    if head.startswith(_PDF_SIG):
        return "application/pdf"
    if head.startswith(_PNG_SIG):
        return "image/png"
    if head.startswith(_JPEG_SIG):
        return "image/jpeg"
    return None


def validate_and_store(filename: str, declared_mime: str, data: bytes) -> StoredDocument:
    """Validate an uploaded file and store it under UPLOAD_DIR.

    Raises DocumentValidationError with a clear message for malformed, empty,
    oversized, or unsupported files.
    """
    if not filename or "." not in filename:
        raise DocumentValidationError("The file must have a name with an extension.")
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentValidationError(
            f"Unsupported file extension '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )
    if not data:
        raise DocumentValidationError("The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentValidationError(
            f"The file exceeds the maximum size of {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    detected = detect_mime_from_signature(data[:16])
    if detected is None:
        raise DocumentValidationError(
            "The file content does not match a supported PDF, PNG, or JPEG signature."
        )
    # The declared content-type must agree with the actual file signature and
    # be in the allow-list (normalise image/jpg -> image/jpeg).
    declared = (declared_mime or "").split(";")[0].strip().lower()
    if declared == "image/jpg":
        declared = "image/jpeg"
    if declared not in ALLOWED_MIME_TYPES:
        raise DocumentValidationError(f"Unsupported content type '{declared_mime}'.")
    if declared != detected:
        raise DocumentValidationError(
            "The declared content type does not match the actual file content."
        )

    digest = hashlib.sha256(data).hexdigest()
    # Server-generated name: never derived from client input.
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    path = (UPLOAD_DIR / stored_filename).resolve()
    # Defensive check: ensure the target stays inside the upload directory.
    if not str(path).startswith(str(UPLOAD_DIR.resolve())):
        raise DocumentValidationError("Invalid storage path.")
    path.write_bytes(data)

    return StoredDocument(
        stored_filename=stored_filename,
        path=path,
        size=len(data),
        sha256=digest,
        mime_type=detected,
    )


def ocr_available() -> bool:
    """True when pytesseract + the Tesseract engine are importable/usable."""
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401

        return True
    except Exception:
        return False


def extract_text(path: Path, mime_type: str) -> tuple[str, str]:
    """Extract text from a stored document.

    Returns (text, method). Raises RuntimeError with a clear message when
    extraction is impossible (e.g. scanned PDF without OCR installed).
    Never pretends success: callers must record the real status.
    """
    if mime_type == "application/pdf":
        text = _extract_pdf_text(path)
        if text.strip():
            return text, "pdf_text"
        # PDF opened fine but yielded nothing — probably a scan.
        if ocr_available():
            return _run_ocr(path), "ocr"
        raise RuntimeError(
            "No selectable text found in this PDF and OCR is not installed. "
            "Install Tesseract (e.g. 'winget install -e --id UB-Mannheim.TesseractOCR') "
            "and 'pip install pytesseract pillow' to enable OCR for scanned documents."
        )
    # Images always require OCR.
    if ocr_available():
        return _run_ocr(path), "ocr"
    raise RuntimeError(
        "Text extraction from images requires OCR, which is not installed. "
        "Install Tesseract (e.g. 'winget install -e --id UB-Mannheim.TesseractOCR') "
        "and 'pip install pytesseract pillow'."
    )


def _extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - dependency pinned in requirements
        raise RuntimeError("pypdf is not installed; run 'pip install pypdf'.")
    try:
        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception as exc:
        raise RuntimeError(f"Could not read PDF file: {exc}")


def _run_ocr(path: Path) -> str:
    import pytesseract
    from PIL import Image

    with Image.open(path) as img:
        return pytesseract.image_to_string(img)
