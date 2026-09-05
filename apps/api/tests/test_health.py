"""Health endpoint contract test."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "doc-intelligence-api"}
    assert response.headers["x-request-id"]


@pytest.mark.parametrize(
    "origin",
    ["http://localhost:5173", "http://127.0.0.1:5173"],
)
def test_local_frontend_origins_are_allowed(origin: str) -> None:
    response = client.get("/api/v1/health", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
