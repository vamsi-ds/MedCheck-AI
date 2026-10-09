"""Patient creation/listing, visits, invalid IDs and malformed requests."""
from fastapi.testclient import TestClient


def test_patient_create_and_list(client: TestClient, staff_headers, doctor_headers):
    resp = client.post("/api/patients", headers=staff_headers, json={
        "first_name": "Syntha", "last_name": "Patient",
        "date_of_birth": "1990-05-05", "sex": "Female",
    })
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["mrn"].startswith("MC-")
    assert created["is_synthetic"] is True

    listing = client.get("/api/patients", headers=doctor_headers, params={"q": created["mrn"]})
    assert listing.status_code == 200
    body = listing.json()
    assert body["total"] >= 1
    assert any(p["id"] == created["id"] for p in body["items"])


def test_patient_create_requires_staff_or_doctor(client: TestClient, patient_headers, admin_headers):
    payload = {"first_name": "No", "last_name": "Access"}
    assert client.post("/api/patients", headers=patient_headers, json=payload).status_code == 403
    assert client.post("/api/patients", headers=admin_headers, json=payload).status_code == 403
    assert client.post("/api/patients", json=payload).status_code == 401


def test_patient_create_validation(client: TestClient, staff_headers):
    resp = client.post("/api/patients", headers=staff_headers, json={"first_name": ""})
    assert resp.status_code == 422


def test_patient_patch(client: TestClient, staff_headers):
    created = client.post("/api/patients", headers=staff_headers,
                          json={"first_name": "Patch", "last_name": "Me"}).json()
    resp = client.patch(f"/api/patients/{created['id']}", headers=staff_headers,
                        json={"phone": "+91-1234567890"})
    assert resp.status_code == 200
    assert resp.json()["phone"] == "+91-1234567890"


def test_invalid_patient_id(client: TestClient, doctor_headers):
    assert client.get("/api/patients/999999", headers=doctor_headers).status_code == 404
    assert client.get("/api/patients/abc", headers=doctor_headers).status_code == 422


def test_visits_create_and_retrieve(client: TestClient, staff_headers, doctor_headers):
    created = client.post("/api/patients", headers=staff_headers,
                          json={"first_name": "Visit", "last_name": "Test"}).json()
    pid = created["id"]
    resp = client.post(f"/api/patients/{pid}/visits", headers=staff_headers, json={
        "visit_date": "2026-09-12", "visit_type": "Consultation",
        "department": "General Medicine", "reason": "Headache",
        "purpose": "Assessment", "outcome": "Follow-up advised",
    })
    assert resp.status_code == 201, resp.text

    visits = client.get(f"/api/patients/{pid}/visits", headers=doctor_headers)
    assert visits.status_code == 200
    items = visits.json()
    assert len(items) == 1
    assert items[0]["visit_date"] == "2026-09-12"
    assert items[0]["department"] == "General Medicine"


def test_visit_validation(client: TestClient, staff_headers):
    created = client.post("/api/patients", headers=staff_headers,
                          json={"first_name": "Bad", "last_name": "Visit"}).json()
    resp = client.post(f"/api/patients/{created['id']}/visits", headers=staff_headers,
                       json={"visit_date": "not-a-date", "visit_type": "x", "department": "x", "reason": "x"})
    assert resp.status_code == 422
