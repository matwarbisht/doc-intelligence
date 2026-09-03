import os

import asyncpg
import pytest

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
