"""Document HTTP contract tests."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user, get_document_service, get_safeguard_service
from app.api.errors import safeguard_violation_handler
from app.api.routes.documents import router
from app.domain import AuthenticatedUser
from app.services import Capabilities, DocumentService, SafeguardViolation
from tests.fakes import (
    InMemoryDocumentRepository,
    InMemoryObjectStorage,
    unrestricted_safeguards,
)

TEST_USER = AuthenticatedUser(
    id=UUID("10000000-0000-4000-8000-000000000001"), email="alice@example.test"
)
OTHER_USER = AuthenticatedUser(
    id=UUID("20000000-0000-4000-8000-000000000002"), email="bob@example.test"
)


def create_test_client(service: DocumentService) -> tuple[FastAPI, TestClient]:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_document_service] = lambda: service
    application.dependency_overrides[get_current_user] = lambda: TEST_USER
    application.dependency_overrides[get_safeguard_service] = unrestricted_safeguards
    return application, TestClient(application)


def test_upload_and_list_document_contract() -> None:
    repository = InMemoryDocumentRepository()
    service = DocumentService(repository, InMemoryObjectStorage())
    application, client = create_test_client(service)

    try:
        upload_response = client.post(
            "/api/v1/documents",
            files={"file": ("notes.txt", b"Hello documents", "text/plain")},
        )
        list_response = client.get("/api/v1/documents")
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert upload_response.status_code == 201
    assert upload_response.json()["document"]["status"] == "queued"
    assert upload_response.json()["document"]["size_bytes"] == 15
    assert upload_response.json()["duplicate"] is False
    assert list_response.status_code == 200
    assert [item["filename"] for item in list_response.json()["items"]] == ["notes.txt"]


def test_duplicate_upload_returns_existing_document() -> None:
    service = DocumentService(InMemoryDocumentRepository(), InMemoryObjectStorage())
    application, client = create_test_client(service)

    try:
        first = client.post(
            "/api/v1/documents",
            files={"file": ("notes.txt", b"Same", "text/plain")},
        )
        duplicate = client.post(
            "/api/v1/documents",
            files={"file": ("copy.txt", b"Same", "text/plain")},
        )
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["document"]["id"] == first.json()["document"]["id"]


def test_document_detail_exposes_processing_and_intelligence_shape() -> None:
    service = DocumentService(InMemoryDocumentRepository(), InMemoryObjectStorage())
    application, client = create_test_client(service)

    try:
        uploaded = client.post(
            "/api/v1/documents",
            files={"file": ("notes.txt", b"Document details", "text/plain")},
        ).json()
        response = client.get(f"/api/v1/documents/{uploaded['document']['id']}")
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert response.status_code == 200
    detail = response.json()
    assert detail["processing"] == []
    assert detail["extraction"] is None
    assert detail["entities"] == []
    assert detail["facts"] == []
    assert detail["relationships"] == []
    assert detail["sources"] == []
    assert detail["chunk_count"] == 0
    assert detail["embedding_count"] == 0


def test_rejects_unsupported_upload() -> None:
    service = DocumentService(InMemoryDocumentRepository(), InMemoryObjectStorage())
    application, client = create_test_client(service)

    try:
        response = client.post(
            "/api/v1/documents",
            files={"file": ("photo.png", b"not an image", "image/png")},
        )
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert response.status_code == 415
    assert response.json()["detail"].startswith("Unsupported document type")


def test_disabled_upload_is_rejected_before_storage() -> None:
    storage = InMemoryObjectStorage()
    safeguards = unrestricted_safeguards()
    safeguards.capabilities = Capabilities(True, False, True, True, True)
    application, client = create_test_client(DocumentService(InMemoryDocumentRepository(), storage))
    application.add_exception_handler(SafeguardViolation, safeguard_violation_handler)
    application.dependency_overrides[get_safeguard_service] = lambda: safeguards

    try:
        response = client.post(
            "/api/v1/documents",
            files={"file": ("notes.txt", b"must not persist", "text/plain")},
        )
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["code"] == "uploads_disabled"
    assert storage.objects == {}


def test_process_endpoint_requires_a_configured_parser() -> None:
    service = DocumentService(InMemoryDocumentRepository(), InMemoryObjectStorage())
    application, client = create_test_client(service)

    try:
        response = client.post("/api/v1/documents/8f74b58e-82e5-4e0d-adfe-c2dc55bd1fc0/process")
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "Document parsing is not configured."}


def test_document_routes_require_authentication() -> None:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_document_service] = lambda: DocumentService(
        InMemoryDocumentRepository(), InMemoryObjectStorage()
    )
    client = TestClient(application)

    try:
        response = client.get("/api/v1/documents")
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication is required."}


def test_users_cannot_see_or_deduplicate_each_others_documents() -> None:
    repository = InMemoryDocumentRepository()
    service = DocumentService(repository, InMemoryObjectStorage())
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_document_service] = lambda: service
    current_user = {"value": TEST_USER}
    application.dependency_overrides[get_current_user] = lambda: current_user["value"]
    application.dependency_overrides[get_safeguard_service] = unrestricted_safeguards
    client = TestClient(application)

    try:
        alice_upload = client.post(
            "/api/v1/documents",
            files={"file": ("alice.txt", b"private content", "text/plain")},
        ).json()
        current_user["value"] = OTHER_USER
        bob_list = client.get("/api/v1/documents")
        bob_detail = client.get(f"/api/v1/documents/{alice_upload['document']['id']}")
        bob_upload = client.post(
            "/api/v1/documents",
            files={"file": ("bob.txt", b"private content", "text/plain")},
        )
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert bob_list.json()["items"] == []
    assert bob_detail.status_code == 404
    assert bob_upload.status_code == 201
    assert bob_upload.json()["duplicate"] is False
    assert bob_upload.json()["document"]["id"] != alice_upload["document"]["id"]
