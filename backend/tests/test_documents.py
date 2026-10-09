"""Document upload validation: types, signatures, sizes, statuses."""
import io

from fastapi.testclient import TestClient

from app.seed import make_text_pdf


def _upload(client, headers, pid, filename, content, mime):
    return client.post(
        f"/api/patients/{pid}/documents",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), mime)},
        data={"document_type": "consultation", "document_date": "2026-09-12"},
    )


def _mk_patient(client, headers) -> int:
    return client.post("/api/patients", headers=headers,
                       json={"first_name": "Doc", "last_name": "Test"}).json()["id"]


def test_upload_pdf_success_and_status(client: TestClient, staff_headers, doctor_headers):
    pid = _mk_patient(client, staff_headers)
    pdf = make_text_pdf("SYNTHETIC TEST DOCUMENT.\nAllergies: No known drug allergies.\n")
    resp = _upload(client, staff_headers, pid, "note.pdf", pdf, "application/pdf")
    assert resp.status_code == 201, resp.text
    doc = resp.json()
    assert doc["processing_status"] == "completed"
    assert doc["extraction_status"] == "succeeded"

    status_resp = client.get(f"/api/documents/{doc['id']}/status", headers=doctor_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["extraction_status"] == "succeeded"

    detail = client.get(f"/api/documents/{doc['id']}", headers=doctor_headers)
    assert detail.status_code == 200
    assert "No known drug allergies" in detail.json()["extracted_text_preview"]


def test_upload_rejects_bad_extension(client: TestClient, staff_headers):
    pid = _mk_patient(client, staff_headers)
    resp = _upload(client, staff_headers, pid, "evil.exe", b"MZ\x90\x00", "application/pdf")
    assert resp.status_code == 422
    assert "extension" in resp.json()["detail"].lower()


def test_upload_rejects_fake_pdf(client: TestClient, staff_headers):
    """Extension says .pdf but content is not a PDF — magic bytes must catch it."""
    pid = _mk_patient(client, staff_headers)
    resp = _upload(client, staff_headers, pid, "fake.pdf", b"just some text, no signature",
                   "application/pdf")
    assert resp.status_code == 422


def test_upload_rejects_mismatched_mime(client: TestClient, staff_headers):
    """Real PDF bytes declared as image/png — declared type must match signature."""
    pid = _mk_patient(client, staff_headers)
    pdf = make_text_pdf("hello")
    resp = _upload(client, staff_headers, pid, "mismatch.pdf", pdf, "image/png")
    assert resp.status_code == 422
    assert "content type" in resp.json()["detail"].lower()


def test_upload_rejects_empty_file(client: TestClient, staff_headers):
    pid = _mk_patient(client, staff_headers)
    resp = _upload(client, staff_headers, pid, "empty.pdf", b"", "application/pdf")
    assert resp.status_code == 422
    assert "empty" in resp.json()["detail"].lower()


def test_upload_requires_auth(client: TestClient, staff_headers):
    pid = _mk_patient(client, staff_headers)
    resp = client.post(f"/api/patients/{pid}/documents",
                       files={"file": ("a.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")})
    assert resp.status_code == 401


def test_document_metadata_patch(client: TestClient, staff_headers):
    pid = _mk_patient(client, staff_headers)
    pdf = make_text_pdf("SYNTHETIC.")
    doc = _upload(client, staff_headers, pid, "meta.pdf", pdf, "application/pdf").json()
    resp = client.patch(f"/api/documents/{doc['id']}", headers=staff_headers,
                        json={"document_type": "emergency", "document_date": "2026-10-02"})
    assert resp.status_code == 200
    assert resp.json()["document_type"] == "emergency"
