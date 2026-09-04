import os
from contextlib import suppress
from uuid import uuid4

import asyncpg
import httpx
import pytest

from app.db import create_database_pool
from app.providers import ObjectStorageError, ParsedDocument, ParsedElement, SupabaseObjectStorage
from app.repositories import PostgresDocumentRepository, PostgresProcessingRepository
from app.services import DocumentProcessingService, DocumentService

pytestmark = pytest.mark.integration


class IntegrationParser:
    provider_name = "integration-parser"
    provider_version = "1.0"

    async def parse(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> ParsedDocument:
        assert filename == "integration-parse.txt"
        assert content_type == "text/plain"
        assert content
        return ParsedDocument(
            elements=(
                ParsedElement(
                    provider_id="heading",
                    category="Title",
                    text="Integration",
                    page_number=1,
                ),
                ParsedElement(
                    provider_id="paragraph",
                    category="NarrativeText",
                    text="Canonical output retains provenance.",
                    page_number=2,
                    parent_provider_id="heading",
                ),
            )
        )


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


@pytest.mark.asyncio
async def test_parsing_persists_canonical_elements_chunks_and_next_stage() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    supabase_url = os.getenv("TEST_SUPABASE_URL")
    service_role_key = os.getenv("TEST_SUPABASE_SERVICE_ROLE_KEY")
    if not database_url or not supabase_url or not service_role_key:
        pytest.skip("set local database, Supabase URL, and service-role test variables")

    pool = await create_database_pool(database_url)
    uploaded_document_id = None
    storage_path = None

    async with httpx.AsyncClient(timeout=10) as client:
        storage = SupabaseObjectStorage(
            client,
            supabase_url=supabase_url,
            service_role_key=service_role_key,
            bucket="documents",
        )
        document_service = DocumentService(PostgresDocumentRepository(pool), storage)
        processing_service = DocumentProcessingService(
            PostgresProcessingRepository(pool),
            storage,
            IntegrationParser(),
        )
        try:
            upload = await document_service.upload(
                filename="integration-parse.txt",
                content_type="text/plain",
                content=f"Integration parse {uuid4()}".encode(),
            )
            uploaded_document_id = upload.document.id
            storage_path = upload.document.storage_path

            processed = await processing_service.process_document(upload.document.id)
            repeated = await processing_service.process_document(upload.document.id)
            lifecycle = await pool.fetchrow(
                """
                select
                  d.status,
                  dv.parser_provider,
                  dv.parser_version,
                  count(distinct de.id) as element_count,
                  count(distinct c.id) as chunk_count,
                  array_agg(distinct pj.stage order by pj.stage) as stages
                from public.documents d
                join public.document_versions dv on dv.document_id = d.id
                join public.document_elements de on de.document_version_id = dv.id
                join public.chunks c on c.document_version_id = dv.id
                join public.processing_jobs pj on pj.document_version_id = dv.id
                where d.id = $1
                group by d.status, dv.parser_provider, dv.parser_version
                """,
                uploaded_document_id,
            )
            provenance = await pool.fetchrow(
                """
                select page_start, page_end, cardinality(source_element_ids) as sources
                from public.chunks
                where document_version_id = (
                  select id from public.document_versions where document_id = $1
                )
                """,
                uploaded_document_id,
            )

            assert processed.claimed is True
            assert repeated.claimed is False
            assert lifecycle is not None
            assert dict(lifecycle) == {
                "status": "extracting",
                "parser_provider": "integration-parser",
                "parser_version": "1.0",
                "element_count": 2,
                "chunk_count": 1,
                "stages": ["extracting", "parsing", "queued"],
            }
            assert provenance is not None
            assert dict(provenance) == {"page_start": 1, "page_end": 2, "sources": 2}
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
