import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db import create_database_pool
from app.repositories import PostgresSafeguardRepository, QuotaLimit, QuotaRejectedError

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_parallel_reservations_cannot_overshoot_a_counter() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL to test an already-migrated Postgres database")

    pool = await create_database_pool(database_url)
    repository = PostgresSafeguardRepository(pool)
    subject_key = f"integration:{uuid4()}"
    window_start = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    limit = QuotaLimit(
        subject_type="global",
        subject_key=subject_key,
        metric="parallel_reservation_test",
        window_start=window_start,
        window_seconds=3_600,
        amount=1,
        limit=1,
        code="test_limit",
        detail="Test limit reached.",
    )
    try:
        results = await asyncio.gather(
            repository.reserve((limit,)),
            repository.reserve((limit,)),
            return_exceptions=True,
        )

        assert sum(not isinstance(result, BaseException) for result in results) == 1
        assert sum(isinstance(result, QuotaRejectedError) for result in results) == 1
        assert (
            await pool.fetchval(
                """
                select used from public.quota_counters
                where subject_type = 'global' and subject_key = $1
                  and metric = 'parallel_reservation_test'
                """,
                subject_key,
            )
            == 1
        )
    finally:
        await pool.execute(
            "delete from public.quota_counters where subject_key = $1",
            subject_key,
        )
        await pool.close()


@pytest.mark.asyncio
async def test_initial_reservation_above_limit_is_rejected() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL to test an already-migrated Postgres database")

    pool = await create_database_pool(database_url)
    repository = PostgresSafeguardRepository(pool)
    subject_key = f"integration:{uuid4()}"
    limit = QuotaLimit(
        subject_type="global",
        subject_key=subject_key,
        metric="initial_reservation_test",
        window_start=datetime.now(UTC).replace(minute=0, second=0, microsecond=0),
        window_seconds=3_600,
        amount=2,
        limit=1,
        code="test_limit",
        detail="Test limit reached.",
    )
    try:
        with pytest.raises(QuotaRejectedError):
            await repository.reserve((limit,))
        assert (
            await pool.fetchval(
                "select count(*) from public.quota_counters where subject_key = $1",
                subject_key,
            )
            == 0
        )
    finally:
        await pool.execute(
            "delete from public.quota_counters where subject_key = $1",
            subject_key,
        )
        await pool.close()


@pytest.mark.asyncio
async def test_provider_outcomes_can_be_recorded_without_corpus_data() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL to test an already-migrated Postgres database")

    pool = await create_database_pool(database_url)
    repository = PostgresSafeguardRepository(pool)
    action = f"provider.integration.{uuid4()}"
    try:
        await repository.record_event(
            user_id=None,
            ip_hash=None,
            action=action,
            outcome="succeeded",
        )
        await repository.record_event(
            user_id=None,
            ip_hash=None,
            action=action,
            outcome="failed",
            code="provider_429",
        )

        rows = await pool.fetch(
            """
            select outcome, code from public.usage_events
            where action = $1 order by created_at
            """,
            action,
        )
        assert [(row["outcome"], row["code"]) for row in rows] == [
            ("succeeded", None),
            ("failed", "provider_429"),
        ]
    finally:
        await pool.execute("delete from public.usage_events where action = $1", action)
        await pool.close()
