"""Persistence boundary for semantic extraction and embedding stages."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain import (
    Chunk,
    ChunkVector,
    Document,
    DocumentVersion,
    ExtractionRun,
    ProcessingJob,
    SemanticExtraction,
)


@dataclass(frozen=True, slots=True)
class EnrichmentClaim:
    document: Document
    version: DocumentVersion
    job: ProcessingJob
    run: ExtractionRun
    chunks: tuple[Chunk, ...]


@dataclass(frozen=True, slots=True)
class EmbeddingClaim:
    document: Document
    version: DocumentVersion
    job: ProcessingJob
    chunks: tuple[Chunk, ...]


class EnrichmentRepository(Protocol):
    async def claim_extraction(
        self,
        document_id: UUID,
        *,
        provider: str,
        model_name: str,
        model_version: str | None,
        prompt_version: str,
        schema_version: str,
        max_attempts: int,
        stale_after_seconds: int,
    ) -> EnrichmentClaim | None: ...

    async def complete_extraction(
        self, claim: EnrichmentClaim, extraction: SemanticExtraction
    ) -> Document: ...

    async def fail_extraction(self, claim: EnrichmentClaim, *, error: str) -> Document: ...

    async def claim_embedding(
        self,
        document_id: UUID,
        *,
        max_attempts: int,
        stale_after_seconds: int,
    ) -> EmbeddingClaim | None: ...

    async def complete_embedding(
        self,
        claim: EmbeddingClaim,
        *,
        provider: str,
        model_name: str,
        model_version: str | None,
        dimension: int,
        vectors: tuple[ChunkVector, ...],
    ) -> Document: ...

    async def fail_embedding(self, claim: EmbeddingClaim, *, error: str) -> Document: ...

    async def complete_indexing(self, document_id: UUID) -> Document | None: ...
