"""Finding retrieval, review decisions, and review-history persistence."""
from fastapi.testclient import TestClient

from app.seed import make_text_pdf


def _mk_patient_with_conflict(client, staff_headers) -> int:
    """Create a patient with two documents that conflict on allergies."""
    pid = client.post("/api/patients", headers=staff_headers,
                      json={"first_name": "Find", "last_name": "Ings"}).json()["id"]
    doc_a = make_text_pdf(
        "SYNTHETIC TEST DOCUMENT.\nPatient: synthetic.\nAllergies: No known drug allergies.\n")
    doc_b = make_text_pdf(
        "SYNTHETIC TEST DOCUMENT.\nPatient: synthetic.\n"
        "Known allergy to Penicillin with hives documented.\n")
    for name, pdf, d in [("a.pdf", doc_a, "2026-09-12"), ("b.pdf", doc_b, "2026-10-02")]:
        resp = client.post(
            f"/api/patients/{pid}/documents", headers=staff_headers,
            files={"file": (name, pdf, "application/pdf")},
            data={"document_type": "consultation", "document_date": d})
        assert resp.status_code == 201, resp.text
    return pid


def test_findings_list_and_detail(client: TestClient, staff_headers, doctor_headers):
    pid = _mk_patient_with_conflict(client, staff_headers)
    findings = client.get(f"/api/patients/{pid}/findings", headers=doctor_headers)
    assert findings.status_code == 200
    items = findings.json()
    assert len(items) >= 1
    allergy = next(f for f in items if f["category"] == "allergy")
    assert allergy["status"] == "needs_review"
    assert allergy["confidence"] > 0
    assert len(allergy["sources"]) == 2
    for src in allergy["sources"]:
        assert src["excerpt"]
        assert src["match_reason"]
    assert allergy["explanation"]

    detail = client.get(f"/api/findings/{allergy['id']}", headers=doctor_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == allergy["id"]


def test_analysis_is_idempotent(client: TestClient, staff_headers, doctor_headers):
    pid = _mk_patient_with_conflict(client, staff_headers)
    before = client.get(f"/api/patients/{pid}/findings", headers=doctor_headers).json()
    client.post(f"/api/patients/{pid}/analyze", headers=staff_headers)
    after = client.get(f"/api/patients/{pid}/findings", headers=doctor_headers).json()
    assert len(before) == len(after)


def test_doctor_review_persists(client: TestClient, staff_headers, doctor_headers):
    pid = _mk_patient_with_conflict(client, staff_headers)
    finding = client.get(f"/api/patients/{pid}/findings", headers=doctor_headers).json()[0]
    resp = client.patch(f"/api/findings/{finding['id']}/review", headers=doctor_headers, json={
        "decision": "verified",
        "reason": "Checked against original source documents on 2026-10-09.",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "verified"
    assert len(body["reviews"]) == 1
    assert body["reviews"][0]["decision"] == "verified"
    assert body["reviews"][0]["reviewer_name"]

    # Persists across requests.
    again = client.get(f"/api/findings/{finding['id']}", headers=doctor_headers).json()
    assert again["status"] == "verified"
    assert len(again["reviews"]) == 1


def test_review_requires_reason(client: TestClient, doctor_headers):
    resp = client.patch("/api/findings/1/review", headers=doctor_headers,
                        json={"decision": "verified", "reason": "ok"})
    assert resp.status_code == 422  # reason too short


def test_review_invalid_decision(client: TestClient, doctor_headers):
    resp = client.patch("/api/findings/1/review", headers=doctor_headers,
                        json={"decision": "looks-good-to-me", "reason": "long enough reason"})
    assert resp.status_code == 422


def test_non_doctor_cannot_review(client: TestClient, staff_headers, patient_headers):
    resp = client.patch("/api/findings/1/review", headers=staff_headers,
                        json={"decision": "verified", "reason": "long enough reason"})
    assert resp.status_code == 403  # records staff make no clinical decisions
    resp = client.patch("/api/findings/1/review", headers=patient_headers,
                        json={"decision": "dismissed", "reason": "long enough reason"})
    assert resp.status_code == 403  # patients never approve clinical findings


def test_finding_404(client: TestClient, doctor_headers):
    assert client.get("/api/findings/999999", headers=doctor_headers).status_code == 404
