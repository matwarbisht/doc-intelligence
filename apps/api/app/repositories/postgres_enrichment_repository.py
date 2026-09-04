"""Postgres persistence for semantic enrichment and embedding stages."""

from __future__ import annotations

from typing import cast
from uuid import UUID, uuid4

import asyncpg
from asyncpg.pool import PoolConnectionProxy

from app.domain import (
    Chunk,
    ChunkVector,
    Document,
    DocumentVersion,
    ExtractionRun,
    ProcessingJob,
    SemanticExtraction,
)
from app.repositories.enrichment_repository import EmbeddingClaim, EnrichmentClaim


class PostgresEnrichmentRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def claim_extraction(
        self,
        document_id: UUID,
        *,
        provider: str,
        model_name: str,
        model_version: str | None,
        prompt_version: str,
        schema_version: str,
        max_attempts: int,
        stale_after_seconds: int,
    ) -> EnrichmentClaim | None:
        async with self._pool.acquire() as connection, connection.transaction():
            records = await self._claim_job(
                connection,
                document_id,
                stage="extracting",
                document_status="extracting",
                max_attempts=max_attempts,
                stale_after_seconds=stale_after_seconds,
            )
            if records is None:
                return None
            document_row, version_row, job_row, chunk_rows = records
            run_row = await connection.fetchrow(
                """
                insert into public.extraction_runs (
                  document_version_id, provider, model_name, model_version,
                  prompt_version, schema_version, status
                ) values ($1, $2, $3, $4, $5, $6, 'running')
                returning *
                """,
                version_row["id"],
                provider,
                model_name,
                model_version,
                prompt_version,
                schema_version,
            )
        if run_row is None:
            raise RuntimeError("database did not return the extraction run")
        return EnrichmentClaim(
            document=self._document(document_row),
            version=DocumentVersion.model_validate(cast(object, dict(version_row))),
            job=ProcessingJob.model_validate(cast(object, dict(job_row))),
            run=ExtractionRun.model_validate(cast(object, dict(run_row))),
            chunks=tuple(Chunk.model_validate(cast(object, dict(row))) for row in chunk_rows),
        )

    async def complete_extraction(
        self, claim: EnrichmentClaim, extraction: SemanticExtraction
    ) -> Document:
        chunk_ids = {chunk.id for chunk in claim.chunks}
        self._validate_sources(extraction, chunk_ids)
        async with self._pool.acquire() as connection, connection.transaction():
            entity_ids: dict[str, UUID] = {}
            for entity in extraction.entities:
                key = entity.name.casefold()
                if key in entity_ids:
                    continue
                entity_id = uuid4()
                entity_ids[key] = entity_id
                await connection.execute(
                    """
                    insert into public.entities (
                      id, extraction_run_id, canonical_name, entity_type, normalized_value
                    ) values ($1, $2, $3, $4, $5)
                    """,
                    entity_id,
                    claim.run.id,
                    entity.name,
                    entity.entity_type.value,
                    entity.normalized_value,
                )
                for mention in entity.mentions:
                    await connection.execute(
                        """
                        insert into public.entity_mentions (
                          entity_id, chunk_id, surface_text, confidence
                        ) values ($1, $2, $3, $4)
                        on conflict do nothing
                        """,
                        entity_id,
                        mention.source_chunk_id,
                        mention.surface_text,
                        mention.confidence,
                    )
            await connection.executemany(
                """
                insert into public.facts (
                  extraction_run_id, source_chunk_id, subject, predicate,
                  object_value, qualifiers, confidence
                ) values ($1, $2, $3, $4, $5, $6, $7)
                """,
                [
                    (
                        claim.run.id,
                        fact.source_chunk_id,
                        fact.subject,
                        fact.predicate,
                        fact.object_value,
                        fact.qualifiers,
                        fact.confidence,
                    )
                    for fact in extraction.facts
                ],
            )
            for relationship in extraction.relationships:
                subject_id = entity_ids.get(relationship.subject.casefold())
                if subject_id is None:
                    continue
                object_id = entity_ids.get(relationship.object.casefold())
                await connection.execute(
                    """
                    insert into public.relationships (
                      extraction_run_id, source_chunk_id, subject_entity_id,
                      predicate, object_entity_id, object_text, qualifiers, confidence
                    ) values ($1, $2, $3, $4, $5, $6, $7, $8)
                    """,
                    claim.run.id,
                    relationship.source_chunk_id,
                    subject_id,
                    relationship.predicate,
                    object_id,
                    None if object_id is not None else relationship.object,
                    relationship.qualifiers,
                    relationship.confidence,
                )
            await connection.execute(
                """
                update public.extraction_runs
                set status='succeeded', document_type=$2, summary=$3, topics=$4,
                    error=null, completed_at=now()
                where id=$1
                """,
                claim.run.id,
                extraction.document_type,
                extraction.summary,
                list(dict.fromkeys(extraction.topics)),
            )
            document_row = await self._advance(
                connection,
                claim.job.id,
                claim.version.id,
                claim.document.id,
                next_stage="embedding",
                next_status="embedding",
            )
        return self._document(document_row)

    async def fail_extraction(self, claim: EnrichmentClaim, *, error: str) -> Document:
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """
                update public.extraction_runs
                set status='failed', error=$2, completed_at=now() where id=$1
                """,
                claim.run.id,
                error[:4000],
            )
            row = await self._fail_job(
                connection, claim.job.id, claim.document.id, "extraction_failed", error
            )
        return self._document(row)

    async def claim_embedding(
        self,
        document_id: UUID,
        *,
        max_attempts: int,
        stale_after_seconds: int,
    ) -> EmbeddingClaim | None:
        async with self._pool.acquire() as connection, connection.transaction():
            records = await self._claim_job(
                connection,
                document_id,
                stage="embedding",
                document_status="embedding",
                max_attempts=max_attempts,
                stale_after_seconds=stale_after_seconds,
            )
        if records is None:
            return None
        document_row, version_row, job_row, chunk_rows = records
        return EmbeddingClaim(
            document=self._document(document_row),
            version=DocumentVersion.model_validate(cast(object, dict(version_row))),
            job=ProcessingJob.model_validate(cast(object, dict(job_row))),
            chunks=tuple(Chunk.model_validate(cast(object, dict(row))) for row in chunk_rows),
        )

    async def complete_embedding(
        self,
        claim: EmbeddingClaim,
        *,
        provider: str,
        model_name: str,
        model_version: str | None,
        dimension: int,
        vectors: tuple[ChunkVector, ...],
    ) -> Document:
        expected = {chunk.id for chunk in claim.chunks}
        if {vector.chunk_id for vector in vectors} != expected:
            raise ValueError("embeddings must cover every document chunk exactly once")
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                "delete from public.chunk_embeddings where chunk_id = any($1::uuid[])",
                list(expected),
            )
            await connection.executemany(
                """
                insert into public.chunk_embeddings (
                  chunk_id, provider, model_name, model_version, dimension, embedding
                ) values ($1, $2, $3, $4, $5, $6::text::extensions.vector)
                """,
                [
                    (
                        vector.chunk_id,
                        provider,
                        model_name,
                        model_version,
                        dimension,
                        "[" + ",".join(str(value) for value in vector.values) + "]",
                    )
                    for vector in vectors
                ],
            )
            row = await self._advance(
                connection,
                claim.job.id,
                claim.version.id,
                claim.document.id,
                next_stage="indexing",
                next_status="indexing",
            )
        return self._document(row)

    async def fail_embedding(self, claim: EmbeddingClaim, *, error: str) -> Document:
        async with self._pool.acquire() as connection, connection.transaction():
            row = await self._fail_job(
                connection, claim.job.id, claim.document.id, "embedding_failed", error
            )
        return self._document(row)

    async def complete_indexing(self, document_id: UUID) -> Document | None:
        async with self._pool.acquire() as connection, connection.transaction():
            row = await connection.fetchrow(
                """
                select pj.id job_id, d.id document_id
                from public.documents d
                join public.document_versions dv on dv.document_id=d.id
                join public.processing_jobs pj on pj.document_version_id=dv.id
                where d.id=$1 and pj.stage='indexing' and pj.status in ('pending','failed')
                order by dv.version desc limit 1
                for update of d, pj skip locked
                """,
                document_id,
            )
            if row is None:
                return None
            await connection.execute(
                """
                update public.processing_jobs set status='succeeded', progress=1,
                  attempts=attempts+1, started_at=now(), completed_at=now(), error=null
                where id=$1
                """,
                row["job_id"],
            )
            document_row = await connection.fetchrow(
                "update public.documents set status='ready' where id=$1 returning *",
                document_id,
            )
        return self._document(document_row)

    async def _claim_job(
        self,
        connection: asyncpg.Connection | PoolConnectionProxy[asyncpg.Record],
        document_id: UUID,
        *,
        stage: str,
        document_status: str,
        max_attempts: int,
        stale_after_seconds: int,
    ) -> tuple[asyncpg.Record, asyncpg.Record, asyncpg.Record, list[asyncpg.Record]] | None:
        candidate = await connection.fetchrow(
            """
            select pj.id job_id, dv.id version_id
            from public.documents d
            join public.document_versions dv on dv.document_id=d.id
            join public.processing_jobs pj on pj.document_version_id=dv.id
            where d.id=$1 and pj.stage=$2 and pj.attempts<$3
              and (pj.status in ('pending','failed') or
                (pj.status='running' and pj.started_at < now()-make_interval(secs=>$4)))
            order by dv.version desc limit 1
            for update of d, pj skip locked
            """,
            document_id,
            stage,
            max_attempts,
            stale_after_seconds,
        )
        if candidate is None:
            return None
        job_row = await connection.fetchrow(
            """
            update public.processing_jobs set status='running', progress=0,
              attempts=attempts+1, error=null, started_at=now(), completed_at=null
            where id=$1 returning *
            """,
            candidate["job_id"],
        )
        document_row = await connection.fetchrow(
            "update public.documents set status=$2 where id=$1 returning *",
            document_id,
            document_status,
        )
        version_row = await connection.fetchrow(
            "select * from public.document_versions where id=$1", candidate["version_id"]
        )
        chunks = await connection.fetch(
            """
            select id, document_version_id, ordinal, content, section, page_start,
                   page_end, source_element_ids, content_hash, metadata, created_at
            from public.chunks where document_version_id=$1 order by ordinal
            """,
            candidate["version_id"],
        )
        if document_row is None or version_row is None or job_row is None:
            raise RuntimeError("database did not return claimed enrichment records")
        return document_row, version_row, job_row, list(chunks)

    @staticmethod
    async def _advance(
        connection: asyncpg.Connection | PoolConnectionProxy[asyncpg.Record],
        job_id: UUID,
        version_id: UUID,
        document_id: UUID,
        *,
        next_stage: str,
        next_status: str,
    ) -> asyncpg.Record:
        await connection.execute(
            """
            update public.processing_jobs
            set status='succeeded', progress=1, error=null, completed_at=now()
            where id=$1
            """,
            job_id,
        )
        await connection.execute(
            """
            insert into public.processing_jobs (document_version_id,stage,status)
            values ($1,$2,'pending')
            on conflict (document_version_id,stage) do nothing
            """,
            version_id,
            next_stage,
        )
        row = await connection.fetchrow(
            "update public.documents set status=$2 where id=$1 returning *",
            document_id,
            next_status,
        )
        if row is None:
            raise RuntimeError("database did not return advanced document")
        return row

    @staticmethod
    async def _fail_job(
        connection: asyncpg.Connection | PoolConnectionProxy[asyncpg.Record],
        job_id: UUID,
        document_id: UUID,
        status: str,
        error: str,
    ) -> asyncpg.Record:
        await connection.execute(
            """
            update public.processing_jobs
            set status='failed', error=$2, completed_at=now() where id=$1
            """,
            job_id,
            error[:4000],
        )
        row = await connection.fetchrow(
            "update public.documents set status=$2 where id=$1 returning *",
            document_id,
            status,
        )
        if row is None:
            raise RuntimeError("database did not return failed document")
        return row

    @staticmethod
    def _validate_sources(extraction: SemanticExtraction, chunk_ids: set[UUID]) -> None:
        cited = {
            *(
                mention.source_chunk_id
                for entity in extraction.entities
                for mention in entity.mentions
            ),
            *(fact.source_chunk_id for fact in extraction.facts),
            *(relationship.source_chunk_id for relationship in extraction.relationships),
        }
        if not cited.issubset(chunk_ids):
            raise ValueError("semantic extraction cited an unknown source chunk")

    @staticmethod
    def _document(row: asyncpg.Record | None) -> Document:
        if row is None:
            raise RuntimeError("database did not return a document")
        return Document.model_validate(cast(object, dict(row)))
