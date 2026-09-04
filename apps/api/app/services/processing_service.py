"""Retry-safe orchestration for document parsing and canonicalization."""

from dataclasses import dataclass
from uuid import UUID

from app.domain import Document
from app.providers import DocumentParser, ObjectStorage
from app.repositories import ParsingClaim, ProcessingRepository
from app.services.canonicalization import canonicalize_document
from app.services.chunking import create_chunks


class ProcessingError(RuntimeError):
    """Raised when parsed output cannot produce retrieval-ready content."""


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    claimed: bool
    document: Document | None = None


class DocumentProcessingService:
    def __init__(
        self,
        repository: ProcessingRepository,
        storage: ObjectStorage,
        parser: DocumentParser,
        *,
        max_attempts: int = 3,
        stale_after_seconds: int = 15 * 60,
        max_chunk_characters: int = 2_000,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._parser = parser
        self._max_attempts = max_attempts
        self._stale_after_seconds = stale_after_seconds
        self._max_chunk_characters = max_chunk_characters

    async def process_document(self, document_id: UUID) -> ProcessingResult:
        claim = await self._repository.claim_parsing(
            document_id,
            max_attempts=self._max_attempts,
            stale_after_seconds=self._stale_after_seconds,
        )
        if claim is None:
            return ProcessingResult(claimed=False)

        try:
            document = await self._process_claim(claim)
        except Exception as error:
            failed = await self._repository.fail_parsing(
                claim,
                error=f"{type(error).__name__}: {error}",
            )
            return ProcessingResult(claimed=True, document=failed)
        return ProcessingResult(claimed=True, document=document)

    async def _process_claim(self, claim: ParsingClaim) -> Document:
        content = await self._storage.download(claim.document.storage_path)
        parsed = await self._parser.parse(
            filename=claim.document.filename,
            content_type=claim.document.mime_type,
            content=content,
        )
        elements = canonicalize_document(
            parsed,
            document_version_id=claim.version.id,
        )
        chunks = create_chunks(
            elements,
            document_version_id=claim.version.id,
            max_characters=self._max_chunk_characters,
        )
        if not chunks:
            raise ProcessingError("The parser returned no retrieval-ready text.")

        return await self._repository.complete_parsing(
            claim,
            parser_provider=self._parser.provider_name,
            parser_version=self._parser.provider_version,
            elements=elements,
            chunks=chunks,
        )
