"""FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --host 127.0.0.1 --port 8001
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import ALLOWED_ORIGINS, ensure_dirs
from .database import engine, init_db
from .routers import admin, analytics, auth, documents, findings, patients, visits
from .schemas import HealthOut
from .services.document_service import ocr_available

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="MedCheck AI API",
    description=(
        "Backend for the MedCheck AI medical-record contradiction detection demo.\n\n"
        "**All data handled by this system must be synthetic.** Findings produced by "
        "the detection service are algorithmic POTENTIAL inconsistencies that require "
        "verification by a qualified healthcare professional. This system does not "
        "provide medical diagnoses."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

for r in (auth.router, patients.router, visits.router, documents.router,
          findings.router, analytics.router, admin.router):
    app.include_router(r)


@app.on_event("startup")
def _startup() -> None:
    ensure_dirs()
    init_db()
    # Seed synthetic demo data on a fresh database (dev convenience).
    from .seed import seed_if_empty
    seed_if_empty()


@app.get("/api/health", response_model=HealthOut, tags=["health"])
def health():
    """Liveness + dependency check: DB connectivity and OCR availability."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return HealthOut(status="ok", database="connected",
                     ocr_available=ocr_available(), version=app.version)
