"""Document HTTP contract tests."""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_document_service
from app.api.routes.documents import router
from app.services import DocumentService
from tests.fakes import InMemoryDocumentRepository, InMemoryObjectStorage


def create_test_client(service: DocumentService) -> tuple[FastAPI, TestClient]:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_document_service] = lambda: service
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
