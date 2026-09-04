"""Semantic extraction, embedding, and indexing orchestration."""

from dataclasses import dataclass
from uuid import UUID

from app.domain import Document, ExtractionChunk
from app.providers import EmbeddingProvider, SemanticExtractor
from app.repositories import EnrichmentClaim, EnrichmentRepository


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
    ) -> None:
        self._repository = repository
        self._extractor = extractor
        self._embeddings = embeddings
        self._max_attempts = max_attempts
        self._stale_after_seconds = stale_after_seconds

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
            document = await self._extract(extraction_claim)
            if document.status.value.endswith("_failed"):
                return EnrichmentResult(claimed=True, document=document)

        embedding_claim = await self._repository.claim_embedding(
            document_id,
            max_attempts=self._max_attempts,
            stale_after_seconds=self._stale_after_seconds,
        )
        if embedding_claim is not None:
            claimed = True
            chunks = tuple(
                ExtractionChunk(id=chunk.id, content=chunk.content)
                for chunk in embedding_claim.chunks
            )
            try:
                vectors = await self._embeddings.embed(chunks)
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
                return EnrichmentResult(claimed=True, document=document)

        indexed = await self._repository.complete_indexing(document_id)
        if indexed is not None:
            return EnrichmentResult(claimed=True, document=indexed)
        return EnrichmentResult(claimed=claimed, document=None)

    async def _extract(self, claim: EnrichmentClaim) -> Document:
        chunks = tuple(
            ExtractionChunk(id=chunk.id, content=chunk.content) for chunk in claim.chunks
        )
        try:
            extraction = await self._extractor.extract(chunks)
            return await self._repository.complete_extraction(claim, extraction)
        except Exception as error:
            return await self._repository.fail_extraction(
                claim,
                error=f"{type(error).__name__}: {error}",
            )
