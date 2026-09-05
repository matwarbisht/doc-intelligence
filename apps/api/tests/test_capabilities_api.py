# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnusedFunction=false

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_safeguard_service
from app.api.errors import safeguard_violation_handler
from app.api.router import api_router
from app.services import Capabilities, SafeguardViolation
from tests.fakes import unrestricted_safeguards


def test_capabilities_expose_only_public_feature_availability() -> None:
    service = unrestricted_safeguards()
    service.capabilities = Capabilities(
        public_signup=False,
        uploads=True,
        processing=False,
        processing_retries=False,
        ask=True,
    )
    application = FastAPI()
    application.include_router(api_router, prefix="/api/v1")
    application.dependency_overrides[get_safeguard_service] = lambda: service

    response = TestClient(application).get("/api/v1/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "public_signup": False,
        "uploads": True,
        "processing": False,
        "processing_retries": False,
        "ask": True,
    }


def test_safeguard_error_has_stable_code_and_retry_header() -> None:
    application = FastAPI()
    application.add_exception_handler(SafeguardViolation, safeguard_violation_handler)

    @application.get("/limited")
    async def limited() -> None:
        raise SafeguardViolation(
            status_code=429,
            code="daily_question_limit",
            detail="Daily question limit reached.",
            retry_after_seconds=90,
        )

    response = TestClient(application, raise_server_exceptions=False).get("/limited")

    assert response.status_code == 429
    assert response.headers["retry-after"] == "90"
    assert response.json() == {
        "detail": "Daily question limit reached.",
        "code": "daily_question_limit",
        "retry_after_seconds": 90,
    }
