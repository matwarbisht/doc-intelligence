"""Persistence boundary for document records."""

from typing import Protocol
from uuid import UUID

from app.domain import Document, DocumentStatus, DocumentVersion, NewDocument


class DuplicateDocumentError(RuntimeError):
    """Raised when a document with the same content hash already exists."""


class DocumentRepository(Protocol):
    async def create(self, document: NewDocument) -> Document: ...

    async def get(self, document_id: UUID) -> Document | None: ...

    async def get_by_content_hash(self, content_hash: str) -> Document | None: ...

    async def create_queued(self, document: NewDocument) -> Document: ...

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Document]: ...

    async def update_status(self, document_id: UUID, status: DocumentStatus) -> Document | None: ...

    async def create_version(
        self,
        document_id: UUID,
        *,
        parser_provider: str | None = None,
        parser_version: str | None = None,
    ) -> DocumentVersion: ...
