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
from app.repositories.postgres_profile_repository import PostgresProfileRepository
from app.repositories.postgres_query_repository import PostgresQueryRepository
from app.repositories.postgres_safeguard_repository import PostgresSafeguardRepository
from app.repositories.processing_repository import ParsingClaim, ProcessingRepository
from app.repositories.profile_repository import ProfileRepository
from app.repositories.query_repository import QueryRepository
from app.repositories.safeguard_repository import (
    QuotaLimit,
    QuotaRejectedError,
    QuotaReservation,
    QuotaUsage,
    SafeguardRepository,
)

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
    "PostgresProfileRepository",
    "PostgresQueryRepository",
    "PostgresSafeguardRepository",
    "ProcessingRepository",
    "ProfileRepository",
    "QueryRepository",
    "QuotaLimit",
    "QuotaRejectedError",
    "QuotaReservation",
    "QuotaUsage",
    "SafeguardRepository",
]
