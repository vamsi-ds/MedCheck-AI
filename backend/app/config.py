"""Application configuration loaded from environment variables (.env supported).

Defaults are safe for local Windows development. Nothing here contains real
credentials; the development secret key is explicitly marked as dev-only and
the README explains how to set a real one for any shared deployment.
"""
from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"
UPLOAD_DIR = Path(os.environ.get("MEDCHECK_UPLOAD_DIR", str(BACKEND_DIR / "uploads")))

# SQLite by default; set MEDCHECK_DATABASE_URL to a postgresql:// URL later to
# migrate without code changes.
DATABASE_URL = os.environ.get(
    "MEDCHECK_DATABASE_URL", f"sqlite:///{(DATA_DIR / 'medcheck.db').as_posix()}"
)

# Dev-only signing key. Override in any shared environment!
SECRET_KEY = os.environ.get("MEDCHECK_SECRET_KEY", "dev-only-insecure-secret-change-me")
SECRET_KEY_IS_DEV = SECRET_KEY == "dev-only-insecure-secret-change-me"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("MEDCHECK_TOKEN_EXPIRE_MINUTES", "720"))

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "MEDCHECK_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]

# Upload constraints
MAX_UPLOAD_BYTES = int(os.environ.get("MEDCHECK_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))  # 10 MB
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

# Creation of the very first administrator is only possible when this is "1"
# (development) AND the endpoint is called from a non-production setting.
ALLOW_DEV_ADMIN_BOOTSTRAP = os.environ.get("MEDCHECK_DEV_ADMIN_BOOTSTRAP", "1") == "1"


def ensure_dirs() -> None:
    """Create runtime directories (data + uploads) if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
