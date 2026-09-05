import os
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from app.commands.claim_legacy_ownership import (
    OwnershipBackfillError,
    claim_legacy_ownership,
)

pytestmark = pytest.mark.integration
OWNERSHIP_CONTRACT = (
    Path(__file__).parents[3]
    / "supabase"
    / "migrations"
    / "20260905020100_enforce_document_ownership.sql"
)


@pytest.mark.asyncio
async def test_legacy_ownership_dry_run_and_transactional_apply() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL to test an already-migrated Postgres database")

    connection = await asyncpg.connect(database_url)
    transaction = connection.transaction()
    await transaction.start()
    owner_id = uuid4()
    document_id = uuid4()
    query_id = uuid4()
    try:
        await connection.execute("alter table public.documents alter column owner_id drop not null")
        await connection.execute("alter table public.queries alter column user_id drop not null")
        await connection.execute(
            """
            insert into auth.users (id, email, raw_user_meta_data, raw_app_meta_data)
            values ($1, $2, '{}'::jsonb, '{}'::jsonb)
            """,
            owner_id,
            f"backfill-{owner_id}@example.test",
        )
        await connection.execute(
            """
            insert into public.documents (
              id, filename, mime_type, storage_path, content_hash, owner_id
            ) values ($1, 'legacy.txt', 'text/plain', $2, $3, null)
            """,
            document_id,
            f"legacy/{document_id}.txt",
            f"legacy:{document_id}",
        )
        await connection.execute(
            """
            insert into public.queries (id, query_text, query_type, document_id, user_id)
            values ($1, 'Legacy question', 'hybrid', $2, null)
            """,
            query_id,
            document_id,
        )

        dry_run = await claim_legacy_ownership(connection, owner_id)
        assert dry_run.applied is False
        assert dry_run.before.documents == 1
        assert dry_run.before.queries == 1
        assert dry_run.before.missing_storage_objects == 1
        assert (
            await connection.fetchval(
                "select owner_id from public.documents where id = $1", document_id
            )
            is None
        )

        applied = await claim_legacy_ownership(connection, owner_id, apply=True)
        assert applied.applied is True
        assert applied.after is not None
        assert applied.after.documents == 0
        assert applied.after.queries == 0
        assert (
            await connection.fetchval(
                "select owner_id from public.documents where id = $1", document_id
            )
            == owner_id
        )
        assert (
            await connection.fetchval("select user_id from public.queries where id = $1", query_id)
            == owner_id
        )
    finally:
        await transaction.rollback()
        await connection.close()


@pytest.mark.asyncio
async def test_legacy_ownership_rejects_an_unknown_user() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL to test an already-migrated Postgres database")

    connection = await asyncpg.connect(database_url)
    try:
        with pytest.raises(OwnershipBackfillError, match="No Supabase Auth user exists"):
            await claim_legacy_ownership(connection, uuid4(), apply=True)
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_ownership_contract_applies_cleanly_without_mutating_the_test_database() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL to test an already-migrated Postgres database")

    connection = await asyncpg.connect(database_url)
    transaction = connection.transaction()
    await transaction.start()
    try:
        await connection.execute(OWNERSHIP_CONTRACT.read_text())
        document_owner_required = await connection.fetchval(
            """
            select attnotnull
            from pg_attribute
            where attrelid = 'public.documents'::regclass and attname = 'owner_id'
            """
        )
        query_owner_required = await connection.fetchval(
            """
            select attnotnull
            from pg_attribute
            where attrelid = 'public.queries'::regclass and attname = 'user_id'
            """
        )
        scoped_owner_constraint = await connection.fetchval(
            """
            select exists(
              select 1 from pg_constraint
              where conrelid = 'public.queries'::regclass
                and conname = 'queries_document_owner_fkey'
            )
            """
        )

        assert document_owner_required is True
        assert query_owner_required is True
        assert scoped_owner_constraint is True
    finally:
        await transaction.rollback()
        await connection.close()
