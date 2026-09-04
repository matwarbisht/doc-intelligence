"""Persistence interfaces and adapters."""

from app.repositories.document_repository import DocumentRepository, DuplicateDocumentError
from app.repositories.enrichment_repository import (
    EmbeddingClaim,
    EnrichmentClaim,
    EnrichmentRepository,
)
from app.repositories.postgres_document_repository import PostgresDocumentRepository
from app.repositories.postgres_enrichment_repository import PostgresEnrichmentRepository
from app.repositories.postgres_processing_repository import PostgresProcessingRepository
from app.repositories.postgres_query_repository import PostgresQueryRepository
from app.repositories.processing_repository import ParsingClaim, ProcessingRepository
from app.repositories.query_repository import QueryRepository

__all__ = [
    "DocumentRepository",
    "DuplicateDocumentError",
    "EmbeddingClaim",
    "EnrichmentClaim",
    "EnrichmentRepository",
    "ParsingClaim",
    "PostgresDocumentRepository",
    "PostgresEnrichmentRepository",
    "PostgresProcessingRepository",
    "PostgresQueryRepository",
    "ProcessingRepository",
    "QueryRepository",
]
