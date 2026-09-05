"""Persistence contracts for durable safeguards."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class QuotaLimit:
    subject_type: str
    subject_key: str
    metric: str
    window_start: datetime
    window_seconds: int
    amount: int
    limit: int
    code: str
    detail: str
    service_unavailable: bool = False


@dataclass(frozen=True, slots=True)
class QuotaUsage:
    limit: QuotaLimit
    used: int


@dataclass(frozen=True, slots=True)
class QuotaReservation:
    usages: tuple[QuotaUsage, ...]


class QuotaRejectedError(RuntimeError):
    def __init__(self, limit: QuotaLimit) -> None:
        super().__init__(limit.detail)
        self.limit = limit


class SafeguardRepository(Protocol):
    async def reserve(
        self,
        limits: tuple[QuotaLimit, ...],
        *,
        document_owner_id: UUID | None = None,
        max_documents: int | None = None,
    ) -> QuotaReservation: ...

    async def release(self, reservation: QuotaReservation) -> None: ...

    async def record_event(
        self,
        *,
        user_id: UUID | None,
        ip_hash: str | None,
        action: str,
        outcome: str,
        code: str | None = None,
        amount: int = 1,
    ) -> None: ...

    async def register_alert(self, usage: QuotaUsage, threshold: int) -> bool: ...

    async def cleanup(self, *, before: datetime) -> int: ...
