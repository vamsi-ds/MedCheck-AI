"""Authentication, registration-approval workflow, and role permission tests."""
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import User, UserRole, UserStatus


def test_login_and_me(client: TestClient, doctor_headers):
    resp = client.get("/api/auth/me", headers=doctor_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "doc"
    assert body["role"] == "doctor"
    assert body["status"] == "active"
    assert "password" not in body and "password_hash" not in body


def test_login_bad_password(client: TestClient):
    resp = client.post("/api/auth/login", json={"username": "doc", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_token(client: TestClient):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_registration_requires_admin_approval(client: TestClient):
    resp = client.post("/api/auth/register", json={
        "username": "newdoc", "email": "newdoc@medcheckdemo.com",
        "full_name": "New Doctor", "password": "StrongPass123!", "role": "doctor",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"

    # Pending users cannot log in.
    login = client.post("/api/auth/login", json={"username": "newdoc", "password": "StrongPass123!"})
    assert login.status_code == 403
    assert "approval" in login.json()["detail"].lower()

    # Duplicate registration is rejected.
    dup = client.post("/api/auth/register", json={
        "username": "newdoc", "email": "other@medcheckdemo.com",
        "full_name": "New Doctor", "password": "StrongPass123!", "role": "doctor",
    })
    assert dup.status_code == 409


def test_cannot_self_assign_admin_role(client: TestClient):
    resp = client.post("/api/auth/register", json={
        "username": "sneaky", "email": "sneaky@medcheckdemo.com",
        "full_name": "Sneaky Admin", "password": "StrongPass123!", "role": "admin",
    })
    # "admin" is not an allowed registration role; schema validation rejects it.
    assert resp.status_code == 422


def test_admin_can_approve_and_login(client: TestClient, admin_headers):
    client.post("/api/auth/register", json={
        "username": "approvee", "email": "approvee@medcheckdemo.com",
        "full_name": "Approvee Person", "password": "StrongPass123!", "role": "records_staff",
    })
    users = client.get("/api/admin/users", headers=admin_headers,
                       params={"user_status": "pending"}).json()
    target = next(u for u in users if u["username"] == "approvee")
    resp = client.patch(f"/api/admin/users/{target['id']}", headers=admin_headers,
                        json={"status": "active"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    login = client.post("/api/auth/login", json={"username": "approvee", "password": "StrongPass123!"})
    assert login.status_code == 200


def test_admin_endpoints_require_admin(client: TestClient, doctor_headers, staff_headers, patient_headers):
    for headers in (doctor_headers, staff_headers, patient_headers):
        assert client.get("/api/admin/users", headers=headers).status_code == 403
        assert client.get("/api/admin/audit", headers=headers).status_code == 403
    assert client.get("/api/admin/users").status_code == 401


def test_admin_has_no_clinical_access(client: TestClient, admin_headers, staff_headers):
    created = client.post("/api/patients", headers=staff_headers,
                          json={"first_name": "Clin", "last_name": "Ical"}).json()
    # Admin may not read patient records or create patients.
    assert client.get(f"/api/patients/{created['id']}", headers=admin_headers).status_code == 403
    assert client.get("/api/patients", headers=admin_headers).status_code == 403
    assert client.post("/api/patients", headers=admin_headers,
                       json={"first_name": "X", "last_name": "Y"}).status_code == 403


def test_admin_cannot_review_findings(client: TestClient, admin_headers, staff_headers, doctor_headers):
    """Admins hold no clinical privileges — no finding reviews."""
    pid = client.post("/api/patients", headers=staff_headers,
                      json={"first_name": "Rev", "last_name": "Iew"}).json()["id"]
    resp = client.patch("/api/findings/1/review", headers=admin_headers,
                        json={"decision": "verified", "reason": "because admin"})
    assert resp.status_code == 403


def test_admin_cannot_deactivate_self(client: TestClient, admin_headers):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    resp = client.patch(f"/api/admin/users/{me['id']}", headers=admin_headers,
                        json={"status": "inactive"})
    assert resp.status_code == 409


def test_admin_cannot_change_own_role(client: TestClient, admin_headers):
    me = client.get("/api/auth/me", headers=admin_headers).json()
    resp = client.patch(f"/api/admin/users/{me['id']}", headers=admin_headers,
                        json={"role": "doctor"})
    assert resp.status_code == 409


def test_deactivated_user_cannot_login(client: TestClient, admin_headers, staff_headers):
    client.post("/api/auth/register", json={
        "username": "tempstaff", "email": "tempstaff@medcheckdemo.com",
        "full_name": "Temp Staff", "password": "StrongPass123!", "role": "records_staff",
    })
    users = client.get("/api/admin/users", headers=admin_headers,
                       params={"user_status": "pending"}).json()
    target = next(u for u in users if u["username"] == "tempstaff")
    client.patch(f"/api/admin/users/{target['id']}", headers=admin_headers, json={"status": "active"})
    # Now deactivate again and confirm login is blocked.
    client.patch(f"/api/admin/users/{target['id']}", headers=admin_headers, json={"status": "inactive"})
    login = client.post("/api/auth/login", json={"username": "tempstaff", "password": "StrongPass123!"})
    assert login.status_code == 403


def test_passwords_never_stored_plaintext(client: TestClient):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == "doc").first()
        assert user is not None
        assert user.password_hash.startswith("pbkdf2_sha256$")
        assert "DocPass123!" not in user.password_hash
    finally:
        db.close()


def test_seed_users_exist(client: TestClient):
    db = SessionLocal()
    try:
        for username, role in [("doctor1", UserRole.doctor), ("records1", UserRole.records_staff),
                               ("patient1", UserRole.patient)]:
            user = db.query(User).filter(User.username == username).first()
            assert user is not None, f"seed user {username} missing"
            assert user.role == role
            assert user.status == UserStatus.active
    finally:
        db.close()
