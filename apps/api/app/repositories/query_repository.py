"""Persistence boundary for corpus retrieval and query history."""

from typing import Protocol
from uuid import UUID

from app.domain import QueryResult, RetrievalHit


class QueryRepository(Protocol):
    async def search_keyword(
        self, query: str, *, document_id: UUID | None, limit: int
    ) -> tuple[RetrievalHit, ...]: ...

    async def search_semantic(
        self,
        vector: tuple[float, ...],
        *,
        provider: str,
        model_name: str,
        dimension: int,
        document_id: UUID | None,
        limit: int,
    ) -> tuple[RetrievalHit, ...]: ...

    async def search_structured(
        self, query: str, *, document_id: UUID | None, limit: int
    ) -> tuple[RetrievalHit, ...]: ...

    async def save_query(self, result: QueryResult) -> None: ...
