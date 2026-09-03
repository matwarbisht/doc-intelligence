"""Persistence interfaces and adapters."""

from app.repositories.document_repository import DocumentRepository, DuplicateDocumentError
from app.repositories.postgres_document_repository import PostgresDocumentRepository

__all__ = ["DocumentRepository", "DuplicateDocumentError", "PostgresDocumentRepository"]
