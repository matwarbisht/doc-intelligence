"""In-memory test doubles for document workflows."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain import Document, DocumentStatus, DocumentVersion, NewDocument


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[UUID, Document] = {}

    async def create(self, document: NewDocument) -> Document:
        return self._save(document, DocumentStatus.UPLOADED)

    async def create_queued(self, document: NewDocument) -> Document:
        return self._save(document, DocumentStatus.QUEUED)

    async def get(self, document_id: UUID) -> Document | None:
        return self.documents.get(document_id)

    async def get_by_content_hash(self, content_hash: str) -> Document | None:
        return next(
            (
                document
                for document in self.documents.values()
                if document.content_hash == content_hash
            ),
            None,
        )

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Document]:
        documents = sorted(
            self.documents.values(),
            key=lambda document: (document.created_at, document.id),
            reverse=True,
        )
        return documents[offset : offset + limit]

    async def update_status(
        self,
        document_id: UUID,
        status: DocumentStatus,
    ) -> Document | None:
        document = self.documents.get(document_id)
        if document is None:
            return None
        updated = document.model_copy(update={"status": status, "updated_at": datetime.now(UTC)})
        self.documents[document_id] = updated
        return updated

    async def create_version(
        self,
        document_id: UUID,
        *,
        parser_provider: str | None = None,
        parser_version: str | None = None,
    ) -> DocumentVersion:
        return DocumentVersion(
            id=uuid4(),
            document_id=document_id,
            version=1,
            parser_provider=parser_provider,
            parser_version=parser_version,
            created_at=datetime.now(UTC),
        )

    def _save(self, new_document: NewDocument, status: DocumentStatus) -> Document:
        now = datetime.now(UTC)
        document = Document(
            **new_document.model_dump(),
            id=uuid4(),
            status=status,
            created_at=now,
            updated_at=now,
        )
        self.documents[document.id] = document
        return document


class InMemoryObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.deleted: list[str] = []

    async def upload(
        self,
        path: str,
        content: bytes,
        *,
        content_type: str,
    ) -> None:
        self.objects[path] = (content, content_type)

    async def delete(self, path: str) -> None:
        self.objects.pop(path, None)
        self.deleted.append(path)
