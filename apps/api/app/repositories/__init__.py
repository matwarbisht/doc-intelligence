"""Persistence interfaces and adapters."""

from app.repositories.document_repository import DocumentRepository, DuplicateDocumentError
from app.repositories.postgres_document_repository import PostgresDocumentRepository
from app.repositories.postgres_processing_repository import PostgresProcessingRepository
from app.repositories.processing_repository import ParsingClaim, ProcessingRepository

__all__ = [
    "DocumentRepository",
    "DuplicateDocumentError",
    "ParsingClaim",
    "PostgresDocumentRepository",
    "PostgresProcessingRepository",
    "ProcessingRepository",
]
