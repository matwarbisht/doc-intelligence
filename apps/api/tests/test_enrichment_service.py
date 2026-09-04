from datetime import UTC, datetime

# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
from uuid import UUID, uuid4

import pytest

from app.domain import (
    Chunk,
    ChunkVector,
    Document,
    DocumentStatus,
    DocumentVersion,
    ExtractedFact,
    ExtractionRun,
    ExtractionStatus,
    JobStatus,
    ProcessingJob,
    ProcessingStage,
    SemanticExtraction,
)
from app.repositories import EmbeddingClaim, EnrichmentClaim
from app.services import DocumentEnrichmentService


class FakeExtractor:
    provider_name = "fake-llm"
    model_name = "fake-model"
    model_version: str | None = None
    prompt_version = "prompt-v1"
    schema_version = "schema-v1"

    async def extract(self, chunks):  # type: ignore[no-untyped-def]
        return SemanticExtraction(
            document_type="report",
            summary="Revenue grew.",
            topics=("revenue",),
            facts=(
                ExtractedFact(
                    source_chunk_id=chunks[0].id,
                    subject="Acme",
                    predicate="revenue_growth",
                    object_value="24%",
                    confidence=0.9,
                ),
            ),
        )


class FakeEmbeddings:
    provider_name = "fake-embeddings"
    model_name = "fake-vector"
    model_version: str | None = None
    dimension = 3

    async def embed(self, chunks):  # type: ignore[no-untyped-def]
        return tuple(ChunkVector(chunk_id=chunk.id, values=(1.0, 0.0, 0.0)) for chunk in chunks)

    async def embed_query(self, query: str) -> tuple[float, ...]:
        return (1.0, 0.0, 0.0)


class FakeEnrichmentRepository:
    def __init__(self, extraction: EnrichmentClaim, embedding: EmbeddingClaim) -> None:
        self.extraction = extraction
        self.embedding = embedding
        self.extraction_available = True
        self.embedding_available = False
        self.saved_extraction: SemanticExtraction | None = None
        self.saved_vectors: tuple[ChunkVector, ...] = ()

    async def claim_extraction(self, document_id: UUID, **kwargs):  # type: ignore[no-untyped-def]
        if not self.extraction_available:
            return None
        self.extraction_available = False
        return self.extraction

    async def complete_extraction(self, claim, extraction):  # type: ignore[no-untyped-def]
        self.saved_extraction = extraction
        self.embedding_available = True
        return claim.document.model_copy(update={"status": DocumentStatus.EMBEDDING})

    async def fail_extraction(self, claim, *, error):  # type: ignore[no-untyped-def]
        return claim.document.model_copy(update={"status": DocumentStatus.EXTRACTION_FAILED})

    async def claim_embedding(self, document_id: UUID, **kwargs):  # type: ignore[no-untyped-def]
        if not self.embedding_available:
            return None
        self.embedding_available = False
        return self.embedding

    async def complete_embedding(self, claim, *, vectors, **kwargs):  # type: ignore[no-untyped-def]
        self.saved_vectors = vectors
        return claim.document.model_copy(update={"status": DocumentStatus.INDEXING})

    async def fail_embedding(self, claim, *, error):  # type: ignore[no-untyped-def]
        return claim.document.model_copy(update={"status": DocumentStatus.EMBEDDING_FAILED})

    async def complete_indexing(self, document_id: UUID):
        if self.saved_vectors:
            return self.embedding.document.model_copy(update={"status": DocumentStatus.READY})
        return None


def claims() -> tuple[EnrichmentClaim, EmbeddingClaim]:
    now = datetime.now(UTC)
    document_id, version_id = uuid4(), uuid4()
    document = Document(
        id=document_id,
        filename="report.txt",
        mime_type="text/plain",
        storage_path="originals/report.txt",
        content_hash="hash",
        status=DocumentStatus.EXTRACTING,
        created_at=now,
        updated_at=now,
    )
    version = DocumentVersion(id=version_id, document_id=document_id, version=1, created_at=now)
    chunk = Chunk(
        id=uuid4(),
        document_version_id=version_id,
        ordinal=0,
        content="Revenue grew 24%.",
        content_hash="chunk-hash",
        created_at=now,
    )
    extraction_job = ProcessingJob(
        id=uuid4(),
        document_version_id=version_id,
        stage=ProcessingStage.EXTRACTING,
        status=JobStatus.RUNNING,
        attempts=1,
        created_at=now,
        updated_at=now,
    )
    run = ExtractionRun(
        id=uuid4(),
        document_version_id=version_id,
        provider="fake-llm",
        model_name="fake-model",
        prompt_version="prompt-v1",
        schema_version="schema-v1",
        status=ExtractionStatus.RUNNING,
        created_at=now,
    )
    embedding_job = ProcessingJob(
        id=uuid4(),
        document_version_id=version_id,
        stage=ProcessingStage.EMBEDDING,
        status=JobStatus.RUNNING,
        attempts=1,
        created_at=now,
        updated_at=now,
    )
    return (
        EnrichmentClaim(
            document=document, version=version, job=extraction_job, run=run, chunks=(chunk,)
        ),
        EmbeddingClaim(document=document, version=version, job=embedding_job, chunks=(chunk,)),
    )


@pytest.mark.asyncio
async def test_enrichment_service_reaches_ready_with_extraction_and_embeddings() -> None:
    extraction, embedding = claims()
    repository = FakeEnrichmentRepository(extraction, embedding)
    service = DocumentEnrichmentService(repository, FakeExtractor(), FakeEmbeddings())

    result = await service.process_document(extraction.document.id)

    assert result.claimed is True
    assert result.document is not None and result.document.status == DocumentStatus.READY
    assert repository.saved_extraction is not None
    assert repository.saved_extraction.facts[0].source_chunk_id == extraction.chunks[0].id
    assert repository.saved_vectors[0].chunk_id == extraction.chunks[0].id
