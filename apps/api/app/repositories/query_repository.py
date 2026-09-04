"""Persistence boundary for corpus retrieval and query history."""

from typing import Protocol

from app.domain import QueryResult, RetrievalHit


class QueryRepository(Protocol):
    async def search_keyword(self, query: str, *, limit: int) -> tuple[RetrievalHit, ...]: ...

    async def search_semantic(
        self,
        vector: tuple[float, ...],
        *,
        provider: str,
        model_name: str,
        dimension: int,
        limit: int,
    ) -> tuple[RetrievalHit, ...]: ...

    async def search_structured(self, query: str, *, limit: int) -> tuple[RetrievalHit, ...]: ...

    async def save_query(self, result: QueryResult) -> None: ...
