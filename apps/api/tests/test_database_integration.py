import os
from contextlib import suppress
from uuid import uuid4

import asyncpg
import httpx
import pytest

from app.db import create_database_pool
from app.providers import ObjectStorageError, SupabaseObjectStorage
from app.repositories import PostgresDocumentRepository
from app.services import DocumentService

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_stage_one_tables_exist_in_configured_database() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("set TEST_DATABASE_URL to test an already-migrated Postgres database")

    connection = await asyncpg.connect(database_url)
    try:
        table_names = await connection.fetchval(
            """
            select array_agg(table_name order by table_name)
            from information_schema.tables
            where table_schema = 'public'
              and table_name = any($1::text[])
            """,
            ["documents", "document_versions", "chunks", "chunk_embeddings"],
        )
    finally:
        await connection.close()

    assert table_names == ["chunk_embeddings", "chunks", "document_versions", "documents"]


@pytest.mark.asyncio
async def test_upload_persists_private_object_and_queued_lifecycle() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    supabase_url = os.getenv("TEST_SUPABASE_URL")
    service_role_key = os.getenv("TEST_SUPABASE_SERVICE_ROLE_KEY")
    if not database_url or not supabase_url or not service_role_key:
        pytest.skip("set local database, Supabase URL, and service-role test variables")

    pool = await create_database_pool(database_url)
    content = f"Integration document {uuid4()}".encode()
    uploaded_document_id = None
    storage_path = None

    async with httpx.AsyncClient(timeout=10) as client:
        storage = SupabaseObjectStorage(
            client,
            supabase_url=supabase_url,
            service_role_key=service_role_key,
            bucket="documents",
        )
        service = DocumentService(PostgresDocumentRepository(pool), storage)
        try:
            result = await service.upload(
                filename="integration-test.txt",
                content_type="text/plain",
                content=content,
            )
            uploaded_document_id = result.document.id
            storage_path = result.document.storage_path

            lifecycle = await pool.fetchrow(
                """
                select
                  d.status as document_status,
                  dv.version,
                  pj.stage,
                  pj.status as job_status,
                  exists(
                    select 1 from storage.objects so
                    where so.bucket_id = 'documents' and so.name = d.storage_path
                  ) as object_exists
                from public.documents d
                join public.document_versions dv on dv.document_id = d.id
                join public.processing_jobs pj on pj.document_version_id = dv.id
                where d.id = $1
                """,
                uploaded_document_id,
            )

            assert lifecycle is not None
            assert dict(lifecycle) == {
                "document_status": "queued",
                "version": 1,
                "stage": "queued",
                "job_status": "pending",
                "object_exists": True,
            }
        finally:
            if storage_path is not None:
                with suppress(ObjectStorageError):
                    await storage.delete(storage_path)
            if uploaded_document_id is not None:
                await pool.execute(
                    "delete from public.documents where id = $1",
                    uploaded_document_id,
                )
            await pool.close()
