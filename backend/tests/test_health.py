"""Health endpoint tests."""
from fastapi.testclient import TestClient


def test_health_ok(client: TestClient):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
    assert isinstance(body["ocr_available"], bool)
