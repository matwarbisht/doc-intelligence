"""Persistence boundary for document records."""

from typing import Protocol
from uuid import UUID

from app.domain import Document, DocumentIntelligence, DocumentStatus, DocumentVersion, NewDocument


class DuplicateDocumentError(RuntimeError):
    """Raised when a document with the same content hash already exists."""


class DocumentRepository(Protocol):
    async def create(self, document: NewDocument) -> Document: ...

    async def get(self, owner_id: UUID, document_id: UUID) -> Document | None: ...

    async def get_intelligence(
        self, owner_id: UUID, document_id: UUID
    ) -> DocumentIntelligence | None: ...

    async def get_by_content_hash(self, owner_id: UUID, content_hash: str) -> Document | None: ...

    async def create_queued(self, document: NewDocument) -> Document: ...

    async def list(self, owner_id: UUID, *, limit: int = 50, offset: int = 0) -> list[Document]: ...

    async def update_status(self, document_id: UUID, status: DocumentStatus) -> Document | None: ...

    async def create_version(
        self,
        document_id: UUID,
        *,
        parser_provider: str | None = None,
        parser_version: str | None = None,
    ) -> DocumentVersion: ...
