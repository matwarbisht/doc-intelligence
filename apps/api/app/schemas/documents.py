"""Document API request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain import (
    Document,
    DocumentIntelligence,
    DocumentStatus,
    EntityType,
    ExtractionStatus,
    JobStatus,
    ProcessingStage,
)


class DocumentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    filename: str
    mime_type: str
    status: DocumentStatus
    size_bytes: int | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, document: Document) -> "DocumentResponse":
        size_bytes = document.metadata.get("size_bytes")
        return cls(
            id=document.id,
            filename=document.filename,
            mime_type=document.mime_type,
            status=document.status,
            size_bytes=size_bytes if isinstance(size_bytes, int) else None,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    duplicate: bool


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    limit: int
    offset: int


class DocumentProcessResponse(BaseModel):
    document_id: UUID
    accepted: bool = True


class ProcessingProgressResponse(BaseModel):
    stage: ProcessingStage
    status: JobStatus
    progress: float
    attempts: int
    error: str | None


class ExtractionSummaryResponse(BaseModel):
    status: ExtractionStatus
    document_type: str | None
    summary: str | None
    topics: list[str]


class EntityResponse(BaseModel):
    id: UUID
    canonical_name: str
    entity_type: EntityType
    normalized_value: str | None


class FactResponse(BaseModel):
    id: UUID
    source_chunk_id: UUID
    subject: str
    predicate: str
    object_value: str
    qualifiers: dict[str, object]
    confidence: float | None


class RelationshipResponse(BaseModel):
    id: UUID
    source_chunk_id: UUID
    subject_entity_id: UUID
    predicate: str
    object_entity_id: UUID | None
    object_text: str | None
    confidence: float | None


class SourceResponse(BaseModel):
    chunk_id: UUID
    filename: str
    page_start: int | None
    page_end: int | None
    excerpt: str


class DocumentDetailResponse(DocumentResponse):
    processing: list[ProcessingProgressResponse]
    extraction: ExtractionSummaryResponse | None
    entities: list[EntityResponse]
    facts: list[FactResponse]
    relationships: list[RelationshipResponse]
    sources: list[SourceResponse]
    chunk_count: int
    embedding_count: int

    @classmethod
    def from_intelligence(cls, intelligence: DocumentIntelligence) -> "DocumentDetailResponse":
        document = intelligence.document
        return cls(
            **DocumentResponse.from_domain(document).model_dump(),
            processing=[
                ProcessingProgressResponse(
                    stage=job.stage,
                    status=job.status,
                    progress=job.progress,
                    attempts=job.attempts,
                    error=job.error,
                )
                for job in intelligence.jobs
            ],
            extraction=(
                ExtractionSummaryResponse(
                    status=intelligence.extraction.status,
                    document_type=intelligence.extraction.document_type,
                    summary=intelligence.extraction.summary,
                    topics=list(intelligence.extraction.topics),
                )
                if intelligence.extraction is not None
                else None
            ),
            entities=[
                EntityResponse(
                    id=entity.id,
                    canonical_name=entity.canonical_name,
                    entity_type=entity.entity_type,
                    normalized_value=entity.normalized_value,
                )
                for entity in intelligence.entities
            ],
            facts=[FactResponse.model_validate(fact.model_dump()) for fact in intelligence.facts],
            relationships=[
                RelationshipResponse.model_validate(relationship.model_dump())
                for relationship in intelligence.relationships
            ],
            sources=[
                SourceResponse.model_validate(source.model_dump())
                for source in intelligence.sources
            ],
            chunk_count=intelligence.chunk_count,
            embedding_count=intelligence.embedding_count,
        )
