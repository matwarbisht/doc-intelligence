from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain import (
    Document,
    DocumentStatus,
    DocumentVersion,
    JobStatus,
    NewCanonicalElement,
    NewChunk,
    ProcessingJob,
    ProcessingStage,
)
from app.providers import DocumentParserError, ParsedDocument, ParsedElement
from app.repositories import ParsingClaim
from app.services import DocumentProcessingService
from tests.fakes import InMemoryObjectStorage


class FakeParser:
    provider_name = "fake-parser"
    provider_version = "1.0"

    def __init__(self, *, fails: bool = False) -> None:
        self.fails = fails

    async def parse(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> ParsedDocument:
        if self.fails:
            raise DocumentParserError("parser unavailable")
        assert filename == "report.pdf"
        assert content_type == "application/pdf"
        assert content == b"pdf"
        return ParsedDocument(
            elements=(
                ParsedElement(provider_id="h1", category="Title", text="Results", page_number=1),
                ParsedElement(
                    provider_id="p1",
                    category="NarrativeText",
                    text="Revenue grew.",
                    page_number=2,
                ),
            )
        )


class FakeProcessingRepository:
    def __init__(self, claim: ParsingClaim) -> None:
        self.claim = claim
        self.available = True
        self.elements: tuple[NewCanonicalElement, ...] = ()
        self.chunks: tuple[NewChunk, ...] = ()
        self.failure: str | None = None

    async def claim_parsing(
        self,
        document_id: UUID,
        *,
        max_attempts: int,
        stale_after_seconds: int,
    ) -> ParsingClaim | None:
        assert max_attempts == 3
        assert stale_after_seconds == 900
        assert document_id == self.claim.document.id
        if not self.available:
            return None
        self.available = False
        return self.claim

    async def complete_parsing(
        self,
        claim: ParsingClaim,
        *,
        parser_provider: str,
        parser_version: str,
        elements: tuple[NewCanonicalElement, ...],
        chunks: tuple[NewChunk, ...],
    ) -> Document:
        assert claim == self.claim
        assert (parser_provider, parser_version) == ("fake-parser", "1.0")
        self.elements = elements
        self.chunks = chunks
        return claim.document.model_copy(update={"status": DocumentStatus.EXTRACTING})

    async def fail_parsing(self, claim: ParsingClaim, *, error: str) -> Document:
        assert claim == self.claim
        self.failure = error
        return claim.document.model_copy(update={"status": DocumentStatus.PARSING_FAILED})


def parsing_claim() -> ParsingClaim:
    now = datetime.now(UTC)
    document_id = uuid4()
    version_id = uuid4()
    return ParsingClaim(
        document=Document(
            id=document_id,
            owner_id=uuid4(),
            filename="report.pdf",
            mime_type="application/pdf",
            storage_path="originals/report.pdf",
            content_hash="hash",
            status=DocumentStatus.PARSING,
            created_at=now,
            updated_at=now,
        ),
        version=DocumentVersion(
            id=version_id,
            document_id=document_id,
            version=1,
            created_at=now,
        ),
        job=ProcessingJob(
            id=uuid4(),
            document_version_id=version_id,
            stage=ProcessingStage.PARSING,
            status=JobStatus.RUNNING,
            attempts=1,
            created_at=now,
            updated_at=now,
        ),
    )


@pytest.mark.asyncio
async def test_processing_service_persists_canonical_output_once() -> None:
    claim = parsing_claim()
    repository = FakeProcessingRepository(claim)
    storage = InMemoryObjectStorage()
    storage.objects[claim.document.storage_path] = (b"pdf", "application/pdf")
    service = DocumentProcessingService(repository, storage, FakeParser())

    first = await service.process_document(claim.document.id)
    second = await service.process_document(claim.document.id)

    assert first.claimed is True
    assert first.document is not None
    assert first.document.status == DocumentStatus.EXTRACTING
    assert len(repository.elements) == 2
    assert len(repository.chunks) == 1
    assert second.claimed is False


@pytest.mark.asyncio
async def test_processing_service_records_parser_failure_for_retry() -> None:
    claim = parsing_claim()
    repository = FakeProcessingRepository(claim)
    storage = InMemoryObjectStorage()
    storage.objects[claim.document.storage_path] = (b"pdf", "application/pdf")
    service = DocumentProcessingService(repository, storage, FakeParser(fails=True))

    result = await service.process_document(claim.document.id)

    assert result.claimed is True
    assert result.document is not None
    assert result.document.status == DocumentStatus.PARSING_FAILED
    assert repository.failure == "DocumentParserError: parser unavailable"

    repository.available = True
    parser = FakeParser()
    retry_service = DocumentProcessingService(repository, storage, parser)

    retry = await retry_service.process_document(claim.document.id)

    assert retry.claimed is True
    assert retry.document is not None
    assert retry.document.status == DocumentStatus.EXTRACTING
    assert repository.chunks
