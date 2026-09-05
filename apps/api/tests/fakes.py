"""In-memory test doubles for document workflows."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain import Document, DocumentIntelligence, DocumentStatus, DocumentVersion, NewDocument
from app.repositories import QuotaLimit, QuotaRejectedError, QuotaReservation, QuotaUsage
from app.services import Capabilities, SafeguardLimits, SafeguardService


class InMemoryDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[UUID, Document] = {}

    async def create(self, document: NewDocument) -> Document:
        return self._save(document, DocumentStatus.UPLOADED)

    async def create_queued(self, document: NewDocument) -> Document:
        return self._save(document, DocumentStatus.QUEUED)

    async def get(self, owner_id: UUID, document_id: UUID) -> Document | None:
        document = self.documents.get(document_id)
        return document if document is not None and document.owner_id == owner_id else None

    async def get_intelligence(
        self, owner_id: UUID, document_id: UUID
    ) -> DocumentIntelligence | None:
        document = await self.get(owner_id, document_id)
        return None if document is None else DocumentIntelligence(document=document)

    async def get_by_content_hash(self, owner_id: UUID, content_hash: str) -> Document | None:
        return next(
            (
                document
                for document in self.documents.values()
                if document.owner_id == owner_id and document.content_hash == content_hash
            ),
            None,
        )

    async def list(self, owner_id: UUID, *, limit: int = 50, offset: int = 0) -> list[Document]:
        documents = sorted(
            (document for document in self.documents.values() if document.owner_id == owner_id),
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

    async def download(self, path: str) -> bytes:
        return self.objects[path][0]


class InMemorySafeguardRepository:
    def __init__(self) -> None:
        self.used: dict[tuple[str, str, str, datetime, int], int] = {}
        self.events: list[tuple[str, str, str | None]] = []
        self.alerts: set[tuple[str, str, str, datetime, int, int]] = set()

    async def reserve(
        self,
        limits: tuple[QuotaLimit, ...],
        *,
        document_owner_id: UUID | None = None,
        max_documents: int | None = None,
    ) -> QuotaReservation:
        pending = dict(self.used)
        usages: list[QuotaUsage] = []
        if document_owner_id is not None and max_documents is not None:
            capacity = QuotaLimit(
                subject_type="user",
                subject_key=str(document_owner_id),
                metric="stored_documents",
                window_start=datetime(1970, 1, 1, tzinfo=UTC),
                window_seconds=2_147_483_647,
                amount=1,
                limit=max_documents,
                code="stored_document_limit",
                detail="Stored document limit reached.",
            )
            key = (
                capacity.subject_type,
                capacity.subject_key,
                capacity.metric,
                capacity.window_start,
                capacity.window_seconds,
            )
            value = pending.get(key, 0) + 1
            if value > max_documents:
                raise QuotaRejectedError(capacity)
            pending[key] = value
            usages.append(QuotaUsage(limit=capacity, used=value))
        for item in limits:
            key = (
                item.subject_type,
                item.subject_key,
                item.metric,
                item.window_start,
                item.window_seconds,
            )
            value = pending.get(key, 0) + item.amount
            if value > item.limit:
                raise QuotaRejectedError(item)
            pending[key] = value
            usages.append(QuotaUsage(limit=item, used=value))
        self.used = pending
        return QuotaReservation(tuple(usages))

    async def release(self, reservation: QuotaReservation) -> None:
        for usage in reservation.usages:
            item = usage.limit
            key = (
                item.subject_type,
                item.subject_key,
                item.metric,
                item.window_start,
                item.window_seconds,
            )
            self.used[key] = max(0, self.used.get(key, 0) - item.amount)

    async def record_event(
        self,
        *,
        user_id: UUID | None,
        ip_hash: str | None,
        action: str,
        outcome: str,
        code: str | None = None,
        amount: int = 1,
    ) -> None:
        del user_id, ip_hash, amount
        self.events.append((action, outcome, code))

    async def register_alert(self, usage: QuotaUsage, threshold: int) -> bool:
        item = usage.limit
        key = (
            item.subject_type,
            item.subject_key,
            item.metric,
            item.window_start,
            item.window_seconds,
            threshold,
        )
        if key in self.alerts:
            return False
        self.alerts.add(key)
        return True

    async def cleanup(self, *, before: datetime) -> int:
        del before
        return 0


def unrestricted_safeguards() -> SafeguardService:
    return SafeguardService(
        InMemorySafeguardRepository(),
        capabilities=Capabilities(True, True, True, True, True),
        limits=SafeguardLimits(
            user_uploads_per_hour=1_000,
            user_documents_per_day=1_000,
            user_upload_bytes_per_day=1_000_000_000,
            user_asks_per_hour=1_000,
            user_asks_per_day=1_000,
            user_retries_per_hour=1_000,
            user_retries_per_day=1_000,
            user_max_documents=1_000,
            retry_cooldown_seconds=1,
            ip_uploads_per_hour=1_000,
            ip_asks_per_hour=1_000,
            global_documents_per_day=10_000,
            global_upload_bytes_per_day=10_000_000_000,
            global_asks_per_day=10_000,
        ),
        ip_hash_salt="test-only-salt",
    )
