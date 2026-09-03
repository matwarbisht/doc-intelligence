"""Persistence interfaces and adapters."""

from app.repositories.document_repository import DocumentRepository
from app.repositories.postgres_document_repository import PostgresDocumentRepository

__all__ = ["DocumentRepository", "PostgresDocumentRepository"]
