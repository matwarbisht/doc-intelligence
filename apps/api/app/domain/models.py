"""Core models shared by processing, retrieval, and persistence layers."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

Metadata = dict[str, object]
StructuredContent = dict[str, object] | list[object]
PositiveInt = Annotated[int, Field(gt=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
Confidence = Annotated[float, Field(ge=0, le=1)]


class DomainModel(BaseModel):
    """Immutable base model for values that cross application boundaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    READY = "ready"
    PARSING_FAILED = "parsing_failed"
    EXTRACTION_FAILED = "extraction_failed"
    EMBEDDING_FAILED = "embedding_failed"
    INDEXING_FAILED = "indexing_failed"


class ProcessingStage(StrEnum):
    QUEUED = "queued"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    EMBEDDING = "embedding"
    INDEXING = "indexing"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExtractionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ElementType(StrEnum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    NARRATIVE_TEXT = "narrative_text"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    IMAGE = "image"
    CAPTION = "caption"
    FOOTER = "footer"
    HEADER = "header"
    UNKNOWN = "unknown"


class EntityType(StrEnum):
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    PRODUCT = "product"
    DATE = "date"
    MONEY = "money"
    PERCENTAGE = "percentage"
    METRIC = "metric"
    EVENT = "event"
    UNKNOWN = "unknown"


class QueryType(StrEnum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    STRUCTURED = "structured"
    HYBRID = "hybrid"


class NewDocument(DomainModel):
    filename: Annotated[str, Field(min_length=1)]
    mime_type: Annotated[str, Field(min_length=1)]
    storage_path: Annotated[str, Field(min_length=1)]
    content_hash: Annotated[str, Field(min_length=1)]
    metadata: Metadata = Field(default_factory=dict)


class Document(NewDocument):
    id: UUID
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime


class DocumentVersion(DomainModel):
    id: UUID
    document_id: UUID
    version: PositiveInt
    parser_provider: str | None = None
    parser_version: str | None = None
    created_at: datetime


class ProcessingJob(DomainModel):
    id: UUID
    document_version_id: UUID
    stage: ProcessingStage
    status: JobStatus
    progress: Annotated[float, Field(ge=0, le=1)] = 0
    attempts: NonNegativeInt = 0
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CanonicalElement(DomainModel):
    id: UUID
    document_version_id: UUID
    ordinal: NonNegativeInt
    element_type: ElementType
    parent_element_id: UUID | None = None
    text_content: str | None = None
    page_number: PositiveInt | None = None
    structured_content: StructuredContent | None = None
    metadata: Metadata = Field(default_factory=dict)
    created_at: datetime


class CanonicalDocument(DomainModel):
    version: DocumentVersion
    elements: tuple[CanonicalElement, ...]


class Chunk(DomainModel):
    id: UUID
    document_version_id: UUID
    ordinal: NonNegativeInt
    content: Annotated[str, Field(min_length=1)]
    content_hash: Annotated[str, Field(min_length=1)]
    section: str | None = None
    page_start: PositiveInt | None = None
    page_end: PositiveInt | None = None
    source_element_ids: tuple[UUID, ...] = ()
    metadata: Metadata = Field(default_factory=dict)
    created_at: datetime

    @model_validator(mode="after")
    def page_range_is_ordered(self) -> Self:
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class ChunkEmbedding(DomainModel):
    id: UUID
    chunk_id: UUID
    provider: Annotated[str, Field(min_length=1)]
    model_name: Annotated[str, Field(min_length=1)]
    model_version: str | None = None
    dimension: PositiveInt
    embedding: tuple[float, ...]
    created_at: datetime

    @model_validator(mode="after")
    def dimension_matches_vector(self) -> Self:
        if len(self.embedding) != self.dimension:
            raise ValueError("dimension must match the number of embedding values")
        return self


class ExtractionRun(DomainModel):
    id: UUID
    document_version_id: UUID
    provider: Annotated[str, Field(min_length=1)]
    model_name: Annotated[str, Field(min_length=1)]
    prompt_version: Annotated[str, Field(min_length=1)]
    schema_version: Annotated[str, Field(min_length=1)]
    status: ExtractionStatus
    model_version: str | None = None
    document_type: str | None = None
    summary: str | None = None
    topics: tuple[str, ...] = ()
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class Entity(DomainModel):
    id: UUID
    extraction_run_id: UUID
    canonical_name: Annotated[str, Field(min_length=1)]
    entity_type: EntityType
    normalized_value: str | None = None
    metadata: Metadata = Field(default_factory=dict)
    created_at: datetime


class EntityMention(DomainModel):
    id: UUID
    entity_id: UUID
    chunk_id: UUID
    surface_text: Annotated[str, Field(min_length=1)]
    confidence: Confidence | None = None
    start_offset: NonNegativeInt | None = None
    end_offset: NonNegativeInt | None = None
    created_at: datetime

    @model_validator(mode="after")
    def offsets_are_ordered(self) -> Self:
        if (
            self.start_offset is not None
            and self.end_offset is not None
            and self.end_offset < self.start_offset
        ):
            raise ValueError("end_offset must be greater than or equal to start_offset")
        return self


class Fact(DomainModel):
    id: UUID
    extraction_run_id: UUID
    source_chunk_id: UUID
    subject: Annotated[str, Field(min_length=1)]
    predicate: Annotated[str, Field(min_length=1)]
    object_value: Annotated[str, Field(min_length=1)]
    qualifiers: Metadata = Field(default_factory=dict)
    confidence: Confidence | None = None
    created_at: datetime


class Relationship(DomainModel):
    id: UUID
    extraction_run_id: UUID
    source_chunk_id: UUID
    subject_entity_id: UUID
    predicate: Annotated[str, Field(min_length=1)]
    object_entity_id: UUID | None = None
    object_text: str | None = None
    qualifiers: Metadata = Field(default_factory=dict)
    confidence: Confidence | None = None
    created_at: datetime

    @model_validator(mode="after")
    def has_exactly_one_object(self) -> Self:
        if (self.object_entity_id is None) == (self.object_text is None):
            raise ValueError("exactly one relationship object must be provided")
        return self


class SourceReference(DomainModel):
    chunk_id: UUID
    document_id: UUID
    filename: str
    page_start: PositiveInt | None = None
    page_end: PositiveInt | None = None
    excerpt: str
