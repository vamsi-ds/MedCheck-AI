"""Patient data isolation: a patient user can never reach another patient's data."""
from fastapi.testclient import TestClient


def _link_patient_user(client, staff_headers, username: str) -> tuple[int, dict[str, str]]:
    """Create a patient record + an approved patient-role user linked to it."""
    from app.database import SessionLocal
    from app.models import User, UserStatus

    patient = client.post("/api/patients", headers=staff_headers,
                          json={"first_name": username.title(), "last_name": "Isolated"}).json()
    client.post("/api/auth/register", json={
        "username": username, "email": f"{username}@medcheckdemo.com",
        "full_name": username.title(), "password": "StrongPass123!", "role": "patient",
    })
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        user.patient_id = patient["id"]
        user.status = UserStatus.active
        db.commit()
    finally:
        db.close()
    login = client.post("/api/auth/login", json={"username": username, "password": "StrongPass123!"})
    assert login.status_code == 200
    return patient["id"], {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_patient_sees_only_own_record(client: TestClient, staff_headers, doctor_headers):
    pid_a, headers_a = _link_patient_user(client, staff_headers, "iso1")
    pid_b, _ = _link_patient_user(client, staff_headers, "iso2")

    # Own record: visible.
    assert client.get(f"/api/patients/{pid_a}", headers=headers_a).status_code == 200
    # Other patient's record: forbidden for direct access and subresources.
    assert client.get(f"/api/patients/{pid_b}", headers=headers_a).status_code == 403
    assert client.get(f"/api/patients/{pid_b}/visits", headers=headers_a).status_code == 403
    assert client.get(f"/api/patients/{pid_b}/documents", headers=headers_a).status_code == 403
    assert client.get(f"/api/patients/{pid_b}/findings", headers=headers_a).status_code == 403
    # And cannot modify the other record.
    assert client.patch(f"/api/patients/{pid_b}", headers=headers_a,
                        json={"phone": "123"}).status_code == 403
    # Cannot create patients at all.
    assert client.post("/api/patients", headers=headers_a,
                       json={"first_name": "No", "last_name": "Way"}).status_code == 403


def test_patient_directory_lists_only_self(client: TestClient, staff_headers):
    pid_a, headers_a = _link_patient_user(client, staff_headers, "iso3")
    listing = client.get("/api/patients", headers=headers_a)
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == pid_a


def test_patient_cannot_upload_or_review(client: TestClient, staff_headers):
    pid_a, headers_a = _link_patient_user(client, staff_headers, "iso4")
    import io
    resp = client.post(f"/api/patients/{pid_a}/documents", headers=headers_a,
                       files={"file": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")})
    assert resp.status_code == 403  # patients do not upload documents
    resp = client.patch("/api/findings/1/review", headers=headers_a,
                        json={"decision": "verified", "reason": "long enough reason"})
    assert resp.status_code == 403  # patients never approve findings


def test_patient_cannot_access_admin(client: TestClient, staff_headers):
    _, headers_a = _link_patient_user(client, staff_headers, "iso5")
    assert client.get("/api/admin/users", headers=headers_a).status_code == 403
    assert client.get("/api/admin/audit", headers=headers_a).status_code == 403


def test_doctor_and_staff_can_see_all(client: TestClient, staff_headers, doctor_headers):
    pid, _ = _link_patient_user(client, staff_headers, "iso6")
    assert client.get(f"/api/patients/{pid}", headers=doctor_headers).status_code == 200
    assert client.get(f"/api/patients/{pid}", headers=staff_headers).status_code == 200
