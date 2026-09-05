"""Postgres implementation of atomic fixed-window safeguards."""

from datetime import UTC, datetime
from uuid import UUID

import asyncpg

from app.repositories.safeguard_repository import (
    QuotaLimit,
    QuotaRejectedError,
    QuotaReservation,
    QuotaUsage,
)


class PostgresSafeguardRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def reserve(
        self,
        limits: tuple[QuotaLimit, ...],
        *,
        document_owner_id: UUID | None = None,
        max_documents: int | None = None,
    ) -> QuotaReservation:
        ordered = tuple(
            sorted(
                limits,
                key=lambda item: (
                    item.subject_type,
                    item.subject_key,
                    item.metric,
                    item.window_start,
                    item.window_seconds,
                ),
            )
        )
        usages: list[QuotaUsage] = []
        async with self._pool.acquire() as connection, connection.transaction():
            if document_owner_id is not None and max_documents is not None:
                await connection.execute(
                    "select pg_advisory_xact_lock(hashtextextended($1, 0))",
                    f"document-capacity:{document_owner_id}",
                )
                document_count = await connection.fetchval(
                    "select count(*) from public.documents where owner_id = $1",
                    document_owner_id,
                )
                capacity_limit = QuotaLimit(
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
                reserved_count = await connection.fetchval(
                    """
                    select used from public.quota_counters
                    where subject_type = 'user' and subject_key = $1
                      and metric = 'stored_documents'
                      and window_start = $2 and window_seconds = $3
                    """,
                    str(document_owner_id),
                    capacity_limit.window_start,
                    capacity_limit.window_seconds,
                )
                baseline = max(int(document_count or 0), int(reserved_count or 0))
                if baseline >= max_documents:
                    raise QuotaRejectedError(capacity_limit)
                capacity_used = baseline + 1
                await connection.execute(
                    """
                    insert into public.quota_counters (
                      subject_type, subject_key, metric, window_start,
                      window_seconds, used
                    ) values ('user', $1, 'stored_documents', $2, $3, $4)
                    on conflict (
                      subject_type, subject_key, metric, window_start, window_seconds
                    )
                    do update set used = excluded.used, updated_at = now()
                    """,
                    str(document_owner_id),
                    capacity_limit.window_start,
                    capacity_limit.window_seconds,
                    capacity_used,
                )
                usages.append(QuotaUsage(limit=capacity_limit, used=capacity_used))
            for item in ordered:
                row = await connection.fetchrow(
                    """
                    insert into public.quota_counters (
                      subject_type, subject_key, metric, window_start,
                      window_seconds, used
                    )
                    select
                      $1::text, $2::text, $3::text, $4::timestamptz,
                      $5::integer, $6::bigint
                    where $6::bigint <= $7::bigint
                    on conflict (
                      subject_type, subject_key, metric, window_start, window_seconds
                    ) do update
                    set used = public.quota_counters.used + excluded.used,
                        updated_at = now()
                    where public.quota_counters.used + excluded.used <= $7
                    returning used
                    """,
                    item.subject_type,
                    item.subject_key,
                    item.metric,
                    item.window_start,
                    item.window_seconds,
                    item.amount,
                    item.limit,
                )
                if row is None:
                    raise QuotaRejectedError(item)
                usages.append(QuotaUsage(limit=item, used=int(row["used"])))
        return QuotaReservation(usages=tuple(usages))

    async def release(self, reservation: QuotaReservation) -> None:
        async with self._pool.acquire() as connection, connection.transaction():
            for usage in reservation.usages:
                item = usage.limit
                await connection.execute(
                    """
                    update public.quota_counters
                    set used = greatest(0, used - $6), updated_at = now()
                    where subject_type = $1 and subject_key = $2 and metric = $3
                      and window_start = $4 and window_seconds = $5
                    """,
                    item.subject_type,
                    item.subject_key,
                    item.metric,
                    item.window_start,
                    item.window_seconds,
                    item.amount,
                )

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
        await self._pool.execute(
            """
            insert into public.usage_events (
              user_id, ip_hash, action, outcome, code, amount
            ) values ($1, $2, $3, $4, $5, $6)
            """,
            user_id,
            ip_hash,
            action,
            outcome,
            code,
            amount,
        )

    async def register_alert(self, usage: QuotaUsage, threshold: int) -> bool:
        item = usage.limit
        result = await self._pool.execute(
            """
            insert into public.quota_alerts (
              subject_type, subject_key, metric, window_start, window_seconds, threshold
            ) values ($1, $2, $3, $4, $5, $6)
            on conflict do nothing
            """,
            item.subject_type,
            item.subject_key,
            item.metric,
            item.window_start,
            item.window_seconds,
            threshold,
        )
        return result == "INSERT 0 1"

    async def cleanup(self, *, before: datetime) -> int:
        result = await self._pool.execute(
            """
            delete from public.quota_counters
            where window_start + make_interval(secs => window_seconds) < $1
            """,
            before,
        )
        return int(result.rsplit(" ", 1)[-1])
