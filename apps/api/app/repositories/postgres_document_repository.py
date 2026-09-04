"""asyncpg implementation of the document repository."""

from typing import cast
from uuid import UUID

import asyncpg

from app.domain import (
    Document,
    DocumentIntelligence,
    DocumentStatus,
    DocumentVersion,
    Entity,
    ExtractionRun,
    Fact,
    NewDocument,
    ProcessingJob,
    Relationship,
    SourceReference,
)
from app.repositories.document_repository import DuplicateDocumentError


class PostgresDocumentRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, document: NewDocument) -> Document:
        row = await self._pool.fetchrow(
            """
            insert into public.documents (
                filename, mime_type, storage_path, content_hash, metadata
            ) values ($1, $2, $3, $4, $5)
            returning *
            """,
            document.filename,
            document.mime_type,
            document.storage_path,
            document.content_hash,
            document.metadata,
        )
        if row is None:
            raise RuntimeError("database did not return the created document")
        return self._to_document(row)

    async def get(self, document_id: UUID) -> Document | None:
        row = await self._pool.fetchrow(
            "select * from public.documents where id = $1",
            document_id,
        )
        return None if row is None else self._to_document(row)

    async def get_intelligence(self, document_id: UUID) -> DocumentIntelligence | None:
        document = await self.get(document_id)
        if document is None:
            return None
        version_id = await self._pool.fetchval(
            """
            select id from public.document_versions
            where document_id=$1 order by version desc limit 1
            """,
            document_id,
        )
        if version_id is None:
            return DocumentIntelligence(document=document)
        jobs = await self._pool.fetch(
            "select * from public.processing_jobs where document_version_id=$1 order by created_at",
            version_id,
        )
        run_row = await self._pool.fetchrow(
            """
            select * from public.extraction_runs
            where document_version_id=$1
            order by (status='succeeded') desc, created_at desc limit 1
            """,
            version_id,
        )
        entities: list[asyncpg.Record] = []
        facts: list[asyncpg.Record] = []
        relationships: list[asyncpg.Record] = []
        if run_row is not None:
            entities = list(
                await self._pool.fetch(
                    """
                    select * from public.entities
                    where extraction_run_id=$1 order by canonical_name
                    """,
                    run_row["id"],
                )
            )
            facts = list(
                await self._pool.fetch(
                    "select * from public.facts where extraction_run_id=$1 order by created_at,id",
                    run_row["id"],
                )
            )
            relationships = list(
                await self._pool.fetch(
                    """
                    select * from public.relationships
                    where extraction_run_id=$1 order by created_at,id
                    """,
                    run_row["id"],
                )
            )
        chunk_rows = await self._pool.fetch(
            """
            select id,page_start,page_end,content from public.chunks
            where document_version_id=$1 order by ordinal
            """,
            version_id,
        )
        embedding_count = await self._pool.fetchval(
            """
            select count(*) from public.chunk_embeddings ce
            join public.chunks c on c.id=ce.chunk_id
            where c.document_version_id=$1
            """,
            version_id,
        )
        return DocumentIntelligence(
            document=document,
            jobs=tuple(ProcessingJob.model_validate(cast(object, dict(row))) for row in jobs),
            extraction=(
                ExtractionRun.model_validate(cast(object, dict(run_row)))
                if run_row is not None
                else None
            ),
            entities=tuple(Entity.model_validate(cast(object, dict(row))) for row in entities),
            facts=tuple(Fact.model_validate(cast(object, dict(row))) for row in facts),
            relationships=tuple(
                Relationship.model_validate(cast(object, dict(row))) for row in relationships
            ),
            sources=tuple(
                SourceReference(
                    chunk_id=row["id"],
                    document_id=document.id,
                    filename=document.filename,
                    page_start=row["page_start"],
                    page_end=row["page_end"],
                    excerpt=row["content"][:500],
                )
                for row in chunk_rows
            ),
            chunk_count=len(chunk_rows),
            embedding_count=int(embedding_count or 0),
        )

    async def get_by_content_hash(self, content_hash: str) -> Document | None:
        row = await self._pool.fetchrow(
            "select * from public.documents where content_hash = $1",
            content_hash,
        )
        return None if row is None else self._to_document(row)

    async def create_queued(self, document: NewDocument) -> Document:
        try:
            async with self._pool.acquire() as connection, connection.transaction():
                row = await connection.fetchrow(
                    """
                    insert into public.documents (
                        filename, mime_type, storage_path, content_hash, metadata
                    ) values ($1, $2, $3, $4, $5)
                    returning *
                    """,
                    document.filename,
                    document.mime_type,
                    document.storage_path,
                    document.content_hash,
                    document.metadata,
                )
                if row is None:
                    raise RuntimeError("database did not return the created document")

                version_id = await connection.fetchval(
                    """
                    insert into public.document_versions (document_id, version)
                    values ($1, 1)
                    returning id
                    """,
                    row["id"],
                )
                await connection.execute(
                    """
                    insert into public.processing_jobs (document_version_id, stage, status)
                    values ($1, 'queued', 'pending')
                    """,
                    version_id,
                )
                queued_row = await connection.fetchrow(
                    """
                    update public.documents
                    set status = 'queued'
                    where id = $1
                    returning *
                    """,
                    row["id"],
                )
        except asyncpg.UniqueViolationError as error:
            raise DuplicateDocumentError from error

        if queued_row is None:
            raise RuntimeError("database did not return the queued document")
        return self._to_document(queued_row)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Document]:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        rows = await self._pool.fetch(
            """
            select * from public.documents
            order by created_at desc, id desc
            limit $1 offset $2
            """,
            limit,
            offset,
        )
        return [self._to_document(row) for row in rows]

    async def update_status(self, document_id: UUID, status: DocumentStatus) -> Document | None:
        row = await self._pool.fetchrow(
            """
            update public.documents
            set status = $2
            where id = $1
            returning *
            """,
            document_id,
            status.value,
        )
        return None if row is None else self._to_document(row)

    async def create_version(
        self,
        document_id: UUID,
        *,
        parser_provider: str | None = None,
        parser_version: str | None = None,
    ) -> DocumentVersion:
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "select pg_advisory_xact_lock(hashtextextended($1::text, 0))",
                document_id,
            )
            row = await connection.fetchrow(
                """
                insert into public.document_versions (
                    document_id, version, parser_provider, parser_version
                )
                select $1, coalesce(max(version), 0) + 1, $2, $3
                from public.document_versions
                where document_id = $1
                returning *
                """,
                document_id,
                parser_provider,
                parser_version,
            )
        if row is None:
            raise RuntimeError("database did not return the created document version")
        return DocumentVersion.model_validate(dict(row))

    @staticmethod
    def _to_document(row: asyncpg.Record) -> Document:
        return Document.model_validate(cast(object, dict(row)))
