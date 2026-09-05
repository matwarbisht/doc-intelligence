"""Semantic extraction, embedding, and indexing orchestration."""

import logging
from dataclasses import dataclass
from uuid import UUID

from app.domain import Document, ExtractionChunk
from app.providers import EmbeddingProvider, SemanticExtractor
from app.repositories import EnrichmentClaim, EnrichmentRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    claimed: bool
    document: Document | None = None


class DocumentEnrichmentService:
    def __init__(
        self,
        repository: EnrichmentRepository,
        extractor: SemanticExtractor,
        embeddings: EmbeddingProvider,
        *,
        max_attempts: int = 3,
        stale_after_seconds: int = 15 * 60,
        max_extraction_chunks: int = 250,
        max_extraction_characters: int = 200_000,
    ) -> None:
        self._repository = repository
        self._extractor = extractor
        self._embeddings = embeddings
        self._max_attempts = max_attempts
        self._stale_after_seconds = stale_after_seconds
        self._max_extraction_chunks = max_extraction_chunks
        self._max_extraction_characters = max_extraction_characters

    async def process_document(self, document_id: UUID) -> EnrichmentResult:
        claimed = False
        extraction_claim = await self._repository.claim_extraction(
            document_id,
            provider=self._extractor.provider_name,
            model_name=self._extractor.model_name,
            model_version=self._extractor.model_version,
            prompt_version=self._extractor.prompt_version,
            schema_version=self._extractor.schema_version,
            max_attempts=self._max_attempts,
            stale_after_seconds=self._stale_after_seconds,
        )
        if extraction_claim is not None:
            claimed = True
            self._log_stage(document_id, "extracting", "started")
            document = await self._extract(extraction_claim)
            if document.status.value.endswith("_failed"):
                self._log_stage(document_id, "extracting", "failed", warning=True)
                return EnrichmentResult(claimed=True, document=document)
            self._log_stage(document_id, "extracting", "succeeded")

        embedding_claim = await self._repository.claim_embedding(
            document_id,
            max_attempts=self._max_attempts,
            stale_after_seconds=self._stale_after_seconds,
        )
        if embedding_claim is not None:
            claimed = True
            self._log_stage(document_id, "embedding", "started")
            chunks = tuple(
                ExtractionChunk(id=chunk.id, content=chunk.content)
                for chunk in embedding_claim.chunks
            )
            try:
                vectors = await self._embeddings.embed(
                    chunks,
                    user_id=embedding_claim.document.owner_id,
                )
                document = await self._repository.complete_embedding(
                    embedding_claim,
                    provider=self._embeddings.provider_name,
                    model_name=self._embeddings.model_name,
                    model_version=self._embeddings.model_version,
                    dimension=self._embeddings.dimension,
                    vectors=vectors,
                )
            except Exception as error:
                document = await self._repository.fail_embedding(
                    embedding_claim,
                    error=f"{type(error).__name__}: {error}",
                )
                self._log_stage(document_id, "embedding", "failed", warning=True)
                return EnrichmentResult(claimed=True, document=document)
            self._log_stage(document_id, "embedding", "succeeded")

        indexed = await self._repository.complete_indexing(document_id)
        if indexed is not None:
            self._log_stage(document_id, "indexing", "succeeded")
            return EnrichmentResult(claimed=True, document=indexed)
        return EnrichmentResult(claimed=claimed, document=None)

    async def _extract(self, claim: EnrichmentClaim) -> Document:
        try:
            if len(claim.chunks) > self._max_extraction_chunks:
                raise ValueError("Document exceeds the configured extraction chunk limit.")
            if sum(len(chunk.content) for chunk in claim.chunks) > self._max_extraction_characters:
                raise ValueError("Document exceeds the configured extraction character limit.")
            chunks = tuple(
                ExtractionChunk(id=chunk.id, content=chunk.content) for chunk in claim.chunks
            )
            extraction = await self._extractor.extract(
                chunks,
                user_id=claim.document.owner_id,
            )
            return await self._repository.complete_extraction(claim, extraction)
        except Exception as error:
            return await self._repository.fail_extraction(
                claim,
                error=f"{type(error).__name__}: {error}",
            )

    @staticmethod
    def _log_stage(document_id: UUID, stage: str, outcome: str, *, warning: bool = False) -> None:
        log = logger.warning if warning else logger.info
        log(
            "Document stage event",
            extra={
                "event": "document.stage.event",
                "document_id": str(document_id),
                "stage": stage,
                "outcome": outcome,
            },
        )
