"""Postgres keyword, vector, and structured retrieval adapter."""

from typing import cast

import asyncpg

from app.domain import QueryResult, QueryType, RetrievalHit

_BASE_COLUMNS = """
    c.id chunk_id, d.id document_id, d.filename, c.content, c.section,
    c.page_start, c.page_end
"""


class PostgresQueryRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def search_keyword(self, query: str, *, limit: int) -> tuple[RetrievalHit, ...]:
        rows = await self._pool.fetch(
            f"""
            select {_BASE_COLUMNS},
                   ts_rank_cd(c.search_vector, websearch_to_tsquery('simple', $1)) score
            from public.chunks c
            join public.document_versions dv on dv.id=c.document_version_id
            join public.documents d on d.id=dv.document_id
            where d.status='ready'
              and dv.id=(select latest.id from public.document_versions latest
                         where latest.document_id=d.id order by latest.version desc limit 1)
              and c.search_vector @@ websearch_to_tsquery('simple', $1)
            order by score desc, c.id
            limit $2
            """,
            query,
            limit,
        )
        return self._hits(rows, QueryType.KEYWORD)

    async def search_semantic(
        self,
        vector: tuple[float, ...],
        *,
        provider: str,
        model_name: str,
        dimension: int,
        limit: int,
    ) -> tuple[RetrievalHit, ...]:
        if len(vector) != dimension:
            raise ValueError("query embedding dimension does not match retrieval configuration")
        vector_type = f"extensions.vector({dimension})"
        vector_text = "[" + ",".join(str(value) for value in vector) + "]"
        rows = await self._pool.fetch(
            f"""
            select {_BASE_COLUMNS},
                   greatest(0, 1-(ce.embedding::{vector_type} <=> $1::text::{vector_type})) score
            from public.chunk_embeddings ce
            join public.chunks c on c.id=ce.chunk_id
            join public.document_versions dv on dv.id=c.document_version_id
            join public.documents d on d.id=dv.document_id
            where d.status='ready' and ce.provider=$2 and ce.model_name=$3 and ce.dimension=$4
              and dv.id=(select latest.id from public.document_versions latest
                         where latest.document_id=d.id order by latest.version desc limit 1)
            order by ce.embedding::{vector_type} <=> $1::text::{vector_type}, c.id
            limit $5
            """,
            vector_text,
            provider,
            model_name,
            dimension,
            limit,
        )
        return self._hits(rows, QueryType.SEMANTIC)

    async def search_structured(self, query: str, *, limit: int) -> tuple[RetrievalHit, ...]:
        rows = await self._pool.fetch(
            f"""
            with matching_chunks as (
              select f.source_chunk_id chunk_id,
                     ts_rank_cd(
                       to_tsvector(
                         'simple', f.subject || ' ' || f.predicate || ' ' || f.object_value
                       ),
                       websearch_to_tsquery('simple', $1)
                     ) score
              from public.facts f
              join public.extraction_runs er on er.id=f.extraction_run_id and er.status='succeeded'
              where to_tsvector(
                      'simple', f.subject || ' ' || f.predicate || ' ' || f.object_value
                    ) @@ websearch_to_tsquery('simple', $1)
              union all
              select em.chunk_id,
                     ts_rank_cd(
                       to_tsvector('simple', e.canonical_name || ' ' || em.surface_text),
                       websearch_to_tsquery('simple', $1)
                     ) score
              from public.entity_mentions em
              join public.entities e on e.id=em.entity_id
              join public.extraction_runs er on er.id=e.extraction_run_id and er.status='succeeded'
              where to_tsvector(
                      'simple', e.canonical_name || ' ' || em.surface_text
                    ) @@ websearch_to_tsquery('simple', $1)
            )
            select {_BASE_COLUMNS}, max(mc.score) score
            from matching_chunks mc
            join public.chunks c on c.id=mc.chunk_id
            join public.document_versions dv on dv.id=c.document_version_id
            join public.documents d on d.id=dv.document_id
            where d.status='ready'
              and dv.id=(select latest.id from public.document_versions latest
                         where latest.document_id=d.id order by latest.version desc limit 1)
            group by c.id, d.id
            order by score desc, c.id
            limit $2
            """,
            query,
            limit,
        )
        return self._hits(rows, QueryType.STRUCTURED)

    async def save_query(self, result: QueryResult) -> None:
        await self._pool.execute(
            """
            insert into public.queries (id, query_text, query_type, response, created_at)
            values ($1, $2, $3, $4, $5)
            """,
            result.id,
            result.query,
            result.query_type.value,
            {
                "answer": result.answer,
                "sources": [source.model_dump(mode="json") for source in result.sources],
            },
            result.created_at,
        )

    @staticmethod
    def _hits(rows: list[asyncpg.Record], match_type: QueryType) -> tuple[RetrievalHit, ...]:
        return tuple(
            RetrievalHit(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                filename=row["filename"],
                content=row["content"],
                section=row["section"],
                page_start=row["page_start"],
                page_end=row["page_end"],
                score=float(cast(float, row["score"])),
                match_types=(match_type,),
            )
            for row in rows
        )
