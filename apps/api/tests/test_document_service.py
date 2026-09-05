import hashlib
from uuid import UUID

import pytest

from app.services import (
    DocumentService,
    EmptyDocumentError,
    FileTooLargeError,
    UnsupportedDocumentTypeError,
)
from tests.fakes import InMemoryDocumentRepository, InMemoryObjectStorage

OWNER_ID = UUID("10000000-0000-4000-8000-000000000001")


@pytest.mark.asyncio
async def test_upload_stores_and_queues_document() -> None:
    repository = InMemoryDocumentRepository()
    storage = InMemoryObjectStorage()
    service = DocumentService(repository, storage)
    content = b"Quarterly results"

    result = await service.upload(
        owner_id=OWNER_ID,
        filename="reports/Quarterly results.txt",
        content_type="text/plain",
        content=content,
    )

    assert result.duplicate is False
    assert result.document.filename == "Quarterly results.txt"
    assert result.document.status == "queued"
    assert result.document.content_hash == hashlib.sha256(content).hexdigest()
    assert result.document.metadata == {"size_bytes": len(content)}
    assert result.document.storage_path.startswith(f"users/{OWNER_ID}/documents/")
    assert result.document.storage_path.endswith("/Quarterly-results.txt")
    assert storage.objects[result.document.storage_path] == (content, "text/plain")


@pytest.mark.asyncio
async def test_duplicate_upload_returns_existing_document_without_storing_again() -> None:
    repository = InMemoryDocumentRepository()
    storage = InMemoryObjectStorage()
    service = DocumentService(repository, storage)

    first = await service.upload(
        owner_id=OWNER_ID,
        filename="notes.md",
        content_type="text/markdown",
        content=b"# Notes",
    )
    second = await service.upload(
        owner_id=OWNER_ID,
        filename="copy.md",
        content_type="text/markdown",
        content=b"# Notes",
    )

    assert second.duplicate is True
    assert second.document.id == first.document.id
    assert len(storage.objects) == 1


@pytest.mark.asyncio
async def test_upload_rejects_empty_oversized_and_unsupported_files() -> None:
    service = DocumentService(
        InMemoryDocumentRepository(),
        InMemoryObjectStorage(),
        max_upload_bytes=4,
    )

    with pytest.raises(EmptyDocumentError):
        await service.upload(
            owner_id=OWNER_ID, filename="empty.txt", content_type="text/plain", content=b""
        )

    with pytest.raises(FileTooLargeError):
        await service.upload(
            owner_id=OWNER_ID,
            filename="large.txt",
            content_type="text/plain",
            content=b"12345",
        )

    with pytest.raises(UnsupportedDocumentTypeError):
        await service.upload(
            owner_id=OWNER_ID,
            filename="image.png",
            content_type="image/png",
            content=b"1234",
        )

    with pytest.raises(UnsupportedDocumentTypeError):
        await service.upload(
            owner_id=OWNER_ID,
            filename="disguised.txt",
            content_type="application/pdf",
            content=b"1234",
        )
