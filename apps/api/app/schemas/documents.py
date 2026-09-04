"""Document API request and response schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain import Document, DocumentStatus


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
