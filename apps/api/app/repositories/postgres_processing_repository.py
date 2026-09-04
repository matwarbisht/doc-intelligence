"""Postgres parsing-job and canonical-output persistence."""

from typing import cast
from uuid import UUID

import asyncpg

from app.domain import (
    Document,
    DocumentVersion,
    NewCanonicalElement,
    NewChunk,
    ProcessingJob,
)
from app.repositories.processing_repository import ParsingClaim


class PostgresProcessingRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def claim_parsing(
        self,
        document_id: UUID,
        *,
        max_attempts: int,
        stale_after_seconds: int,
    ) -> ParsingClaim | None:
        async with self._pool.acquire() as connection, connection.transaction():
            candidate = await connection.fetchrow(
                """
                select pj.id as job_id, pj.stage, dv.id as version_id
                from public.documents d
                join public.document_versions dv on dv.document_id = d.id
                join public.processing_jobs pj on pj.document_version_id = dv.id
                where d.id = $1
                  and pj.stage in ('queued', 'parsing')
                  and pj.attempts < $2
                  and (
                    pj.status in ('pending', 'failed')
                    or (
                      pj.status = 'running'
                      and pj.started_at < now() - make_interval(secs => $3)
                    )
                  )
                order by
                  dv.version desc,
                  case when pj.stage = 'parsing' then 0 else 1 end,
                  pj.created_at desc
                limit 1
                for update of d, pj skip locked
                """,
                document_id,
                max_attempts,
                stale_after_seconds,
            )
            if candidate is None:
                return None

            job_id = candidate["job_id"]
            if candidate["stage"] == "queued":
                await connection.execute(
                    """
                    update public.processing_jobs
                    set status = 'succeeded', progress = 1, completed_at = now()
                    where id = $1
                    """,
                    job_id,
                )
                await connection.execute(
                    """
                    insert into public.processing_jobs (document_version_id, stage, status)
                    values ($1, 'parsing', 'pending')
                    on conflict (document_version_id, stage) do nothing
                    """,
                    candidate["version_id"],
                )
                job_id = await connection.fetchval(
                    """
                    select id
                    from public.processing_jobs
                    where document_version_id = $1
                      and stage = 'parsing'
                      and attempts < $2
                      and (
                        status in ('pending', 'failed')
                        or (
                          status = 'running'
                          and started_at < now() - make_interval(secs => $3)
                        )
                      )
                    for update skip locked
                    """,
                    candidate["version_id"],
                    max_attempts,
                    stale_after_seconds,
                )
                if job_id is None:
                    return None

            job_row = await connection.fetchrow(
                """
                update public.processing_jobs
                set
                  status = 'running',
                  progress = 0,
                  attempts = attempts + 1,
                  error = null,
                  started_at = now(),
                  completed_at = null
                where id = $1
                returning *
                """,
                job_id,
            )
            document_row = await connection.fetchrow(
                """
                update public.documents
                set status = 'parsing'
                where id = $1
                returning *
                """,
                document_id,
            )
            version_row = await connection.fetchrow(
                "select * from public.document_versions where id = $1",
                candidate["version_id"],
            )

        if job_row is None or document_row is None or version_row is None:
            raise RuntimeError("database did not return the claimed parsing records")
        return ParsingClaim(
            document=Document.model_validate(cast(object, dict(document_row))),
            version=DocumentVersion.model_validate(cast(object, dict(version_row))),
            job=ProcessingJob.model_validate(cast(object, dict(job_row))),
        )

    async def complete_parsing(
        self,
        claim: ParsingClaim,
        *,
        parser_provider: str,
        parser_version: str,
        elements: tuple[NewCanonicalElement, ...],
        chunks: tuple[NewChunk, ...],
    ) -> Document:
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """
                update public.document_versions
                set parser_provider = $2, parser_version = $3
                where id = $1
                """,
                claim.version.id,
                parser_provider,
                parser_version,
            )
            await connection.execute(
                "delete from public.chunks where document_version_id = $1",
                claim.version.id,
            )
            await connection.execute(
                "delete from public.document_elements where document_version_id = $1",
                claim.version.id,
            )

            await connection.executemany(
                """
                insert into public.document_elements (
                  id, document_version_id, ordinal, element_type, text_content,
                  page_number, structured_content, metadata
                ) values ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                [
                    (
                        element.id,
                        element.document_version_id,
                        element.ordinal,
                        element.element_type.value,
                        element.text_content,
                        element.page_number,
                        element.structured_content,
                        element.metadata,
                    )
                    for element in elements
                ],
            )
            await connection.executemany(
                """
                update public.document_elements
                set parent_element_id = $2
                where id = $1
                """,
                [
                    (element.id, element.parent_element_id)
                    for element in elements
                    if element.parent_element_id is not None
                ],
            )
            await connection.executemany(
                """
                insert into public.chunks (
                  id, document_version_id, ordinal, content, section, page_start,
                  page_end, source_element_ids, content_hash, metadata
                ) values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                [
                    (
                        chunk.id,
                        chunk.document_version_id,
                        chunk.ordinal,
                        chunk.content,
                        chunk.section,
                        chunk.page_start,
                        chunk.page_end,
                        list(chunk.source_element_ids),
                        chunk.content_hash,
                        chunk.metadata,
                    )
                    for chunk in chunks
                ],
            )
            await connection.execute(
                """
                update public.processing_jobs
                set status = 'succeeded', progress = 1, error = null, completed_at = now()
                where id = $1 and status = 'running'
                """,
                claim.job.id,
            )
            await connection.execute(
                """
                insert into public.processing_jobs (document_version_id, stage, status)
                values ($1, 'extracting', 'pending')
                on conflict (document_version_id, stage) do nothing
                """,
                claim.version.id,
            )
            document_row = await connection.fetchrow(
                """
                update public.documents
                set status = 'extracting'
                where id = $1
                returning *
                """,
                claim.document.id,
            )

        if document_row is None:
            raise RuntimeError("database did not return the parsed document")
        return Document.model_validate(cast(object, dict(document_row)))

    async def fail_parsing(self, claim: ParsingClaim, *, error: str) -> Document:
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(
                """
                update public.processing_jobs
                set status = 'failed', error = $2, completed_at = now()
                where id = $1 and status = 'running'
                """,
                claim.job.id,
                error[:4_000],
            )
            document_row = await connection.fetchrow(
                """
                update public.documents
                set status = 'parsing_failed'
                where id = $1
                returning *
                """,
                claim.document.id,
            )

        if document_row is None:
            raise RuntimeError("database did not return the failed document")
        return Document.model_validate(cast(object, dict(document_row)))
