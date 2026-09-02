"""Health endpoint contract test."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "doc-intelligence-api"}
