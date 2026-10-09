"""Shared pytest fixtures: isolated temp database + app client + demo users."""
from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

# Configure an isolated environment BEFORE importing the app.
_tmpdir = tempfile.mkdtemp(prefix="medcheck_test_")
_posix_tmp = _tmpdir.replace(os.sep, "/")
os.environ["MEDCHECK_DATABASE_URL"] = f"sqlite:///{_posix_tmp}/test.db"
os.environ["MEDCHECK_UPLOAD_DIR"] = f"{_posix_tmp}/uploads"
os.environ["MEDCHECK_DEV_ADMIN_BOOTSTRAP"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, UserRole, UserStatus  # noqa: E402
from app.security import hash_password  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db() -> Iterator[None]:
    Base.metadata.drop_all(bind=engine)
    init_db()
    # Seed synthetic demo data FIRST (it skips when users already exist).
    from app.seed import seed_if_empty
    seed_if_empty()
    db = SessionLocal()
    try:
        for username, role, password in [
            ("doc", UserRole.doctor, "DocPass123!"),
            ("staff", UserRole.records_staff, "StaffPass123!"),
            ("pat", UserRole.patient, "PatPass123!"),
            ("root", UserRole.admin, "RootPass123!"),
        ]:
            db.add(User(
                username=username, email=f"{username}@test.local",
                full_name=username.title(), password_hash=hash_password(password),
                role=role, status=UserStatus.active,
            ))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.fixture(scope="session")
def doctor_headers(client: TestClient) -> dict[str, str]:
    return login(client, "doc", "DocPass123!")


@pytest.fixture(scope="session")
def staff_headers(client: TestClient) -> dict[str, str]:
    return login(client, "staff", "StaffPass123!")


@pytest.fixture(scope="session")
def patient_headers(client: TestClient) -> dict[str, str]:
    return login(client, "pat", "PatPass123!")


@pytest.fixture(scope="session")
def admin_headers(client: TestClient) -> dict[str, str]:
    return login(client, "root", "RootPass123!")
