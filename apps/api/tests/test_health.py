"""Health endpoint contract test."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import api_documentation_paths, app

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


def test_api_documentation_is_available_only_in_development() -> None:
    assert api_documentation_paths("development") == ("/docs", "/openapi.json")
    assert api_documentation_paths("test") == (None, None)
    docs_url, openapi_url = api_documentation_paths("production")
    production_app = FastAPI(docs_url=docs_url, openapi_url=openapi_url, redoc_url=None)
    production_client = TestClient(production_app)

    assert production_client.get("/docs").status_code == 404
    assert production_client.get("/openapi.json").status_code == 404
