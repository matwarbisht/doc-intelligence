"""Corpus-query HTTP schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain import QueryResult, QueryType


class CorpusQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=2_000)


class QuerySourceResponse(BaseModel):
    citation_number: int
    document_id: UUID
    chunk_id: UUID
    filename: str
    section: str | None
    page_start: int | None
    page_end: int | None
    excerpt: str
    score: float
    match_types: list[QueryType]


class CorpusQueryResponse(BaseModel):
    id: UUID
    query: str
    query_type: QueryType
    answer: str
    sources: list[QuerySourceResponse]
    created_at: datetime

    @classmethod
    def from_domain(cls, result: QueryResult) -> "CorpusQueryResponse":
        return cls(
            id=result.id,
            query=result.query,
            query_type=result.query_type,
            answer=result.answer,
            sources=[
                QuerySourceResponse(
                    citation_number=source.citation_number or index,
                    document_id=source.document_id,
                    chunk_id=source.chunk_id,
                    filename=source.filename,
                    section=source.section,
                    page_start=source.page_start,
                    page_end=source.page_end,
                    excerpt=source.content,
                    score=source.score,
                    match_types=list(source.match_types),
                )
                for index, source in enumerate(result.sources, start=1)
            ],
            created_at=result.created_at,
        )
