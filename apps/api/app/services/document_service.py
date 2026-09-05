"""Document upload and lifecycle use cases."""

import hashlib
import re
from contextlib import suppress
from dataclasses import dataclass
from pathlib import PurePath
from uuid import UUID, uuid4

from app.domain import Document, DocumentIntelligence, NewDocument
from app.providers import ObjectStorage, ObjectStorageError
from app.repositories.document_repository import DocumentRepository, DuplicateDocumentError

DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SUPPORTED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/markdown",
        "text/plain",
    }
)
MIME_TYPES_BY_SUFFIX = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}


class DocumentUploadError(ValueError):
    """Base error for a rejected document upload."""


class EmptyDocumentError(DocumentUploadError):
    """Raised when an uploaded file has no content."""


class FileTooLargeError(DocumentUploadError):
    """Raised when an uploaded file exceeds the configured limit."""


class UnsupportedDocumentTypeError(DocumentUploadError):
    """Raised when a file is not a Stage 1 supported type."""


@dataclass(frozen=True, slots=True)
class DocumentUpload:
    document: Document
    duplicate: bool


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        storage: ObjectStorage,
        *,
        max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._max_upload_bytes = max_upload_bytes

    async def upload(
        self,
        *,
        owner_id: UUID,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> DocumentUpload:
        if not content:
            raise EmptyDocumentError("The uploaded document is empty.")
        if len(content) > self._max_upload_bytes:
            raise FileTooLargeError(
                f"The uploaded document exceeds the {self._max_upload_bytes}-byte limit."
            )

        normalized_filename = self._filename(filename)
        normalized_content_type = self._content_type(normalized_filename, content_type)
        content_hash = hashlib.sha256(content).hexdigest()

        existing = await self._repository.get_by_content_hash(owner_id, content_hash)
        if existing is not None:
            return DocumentUpload(document=existing, duplicate=True)

        document_key = uuid4()
        storage_filename = self._storage_filename(normalized_filename)
        storage_path = f"users/{owner_id}/documents/{document_key}/{storage_filename}"
        await self._storage.upload(
            storage_path,
            content,
            content_type=normalized_content_type,
        )

        try:
            document = await self._repository.create_queued(
                NewDocument(
                    owner_id=owner_id,
                    filename=normalized_filename,
                    mime_type=normalized_content_type,
                    storage_path=storage_path,
                    content_hash=content_hash,
                    metadata={"size_bytes": len(content)},
                )
            )
        except DuplicateDocumentError:
            await self._cleanup_storage(storage_path)
            existing = await self._repository.get_by_content_hash(owner_id, content_hash)
            if existing is None:
                raise
            return DocumentUpload(document=existing, duplicate=True)
        except Exception:
            await self._cleanup_storage(storage_path)
            raise

        return DocumentUpload(document=document, duplicate=False)

    async def list_documents(
        self, owner_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Document]:
        return await self._repository.list(owner_id, limit=limit, offset=offset)

    async def get_document(self, owner_id: UUID, document_id: UUID) -> Document | None:
        return await self._repository.get(owner_id, document_id)

    async def get_document_intelligence(
        self, owner_id: UUID, document_id: UUID
    ) -> DocumentIntelligence | None:
        return await self._repository.get_intelligence(owner_id, document_id)

    async def _cleanup_storage(self, storage_path: str) -> None:
        with suppress(ObjectStorageError):
            await self._storage.delete(storage_path)

    @staticmethod
    def _filename(filename: str) -> str:
        name = PurePath(filename).name.strip()
        if not name or name in {".", ".."}:
            raise DocumentUploadError("The uploaded document must have a filename.")
        return name

    @staticmethod
    def _content_type(filename: str, content_type: str | None) -> str:
        inferred = MIME_TYPES_BY_SUFFIX.get(PurePath(filename).suffix.lower())
        if inferred is None:
            supported = ", ".join(sorted(MIME_TYPES_BY_SUFFIX))
            raise UnsupportedDocumentTypeError(
                f"Unsupported document type. Use one of these extensions: {supported}."
            )

        declared = (content_type or "").partition(";")[0].strip().lower()
        if declared in SUPPORTED_MIME_TYPES and declared != inferred:
            raise UnsupportedDocumentTypeError(
                "The document's filename extension and content type do not match."
            )
        return inferred

    @staticmethod
    def _storage_filename(filename: str) -> str:
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", filename).strip("-.")
        return safe_name or "document"
