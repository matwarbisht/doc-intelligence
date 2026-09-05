from uuid import UUID, uuid4

import pytest

from app.domain import (
    GeneratedAnswer,
    GeneratedCitation,
    QueryResult,
    QueryType,
    RetrievalHit,
)
from app.services import CorpusQueryService, EmptyQueryError

TEST_USER_ID = UUID("10000000-0000-4000-8000-000000000001")


def hit(chunk_id: UUID, match_type: QueryType, filename: str) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=chunk_id,
        document_id=uuid4(),
        filename=filename,
        content=f"Evidence from {filename}",
        page_start=2,
        page_end=2,
        score=0.8,
        match_types=(match_type,),
    )


class FakeQueryRepository:
    def __init__(self, keyword, semantic, structured):  # type: ignore[no-untyped-def]
        self.keyword = keyword
        self.semantic = semantic
        self.structured = structured
        self.saved: QueryResult | None = None
        self.semantic_request: dict[str, object] = {}
        self.keyword_document_id: UUID | None = None
        self.structured_document_id: UUID | None = None

    async def search_keyword(  # type: ignore[no-untyped-def]
        self, query: str, *, user_id: UUID, document_id: UUID | None, limit: int
    ):
        assert user_id == TEST_USER_ID
        self.keyword_document_id = document_id
        return self.keyword

    async def search_semantic(self, vector, **kwargs):  # type: ignore[no-untyped-def]
        self.semantic_request = {"vector": vector, **kwargs}
        return self.semantic

    async def search_structured(  # type: ignore[no-untyped-def]
        self, query: str, *, user_id: UUID, document_id: UUID | None, limit: int
    ):
        assert user_id == TEST_USER_ID
        self.structured_document_id = document_id
        return self.structured

    async def save_query(self, result: QueryResult) -> None:
        self.saved = result


class FakeQueryEmbeddings:
    provider_name = "fake"
    model_name = "fake-query-vector"
    model_version: str | None = None
    dimension = 3

    async def embed(self, chunks):  # type: ignore[no-untyped-def]
        return ()

    async def embed_query(self, query: str) -> tuple[float, ...]:
        return (1.0, 0.0, 0.0)


class FakeAnswerGenerator:
    provider_name = "fake"
    model_name = "fake-answer"
    model_version: str | None = None
    prompt_version = "test"
    schema_version = "test"

    async def generate(self, question: str, evidence: tuple[RetrievalHit, ...]):
        return GeneratedAnswer(
            answer="The notes describe the change [2].",
            citations=(GeneratedCitation(source_number=2, chunk_id=evidence[1].chunk_id),),
        )


@pytest.mark.asyncio
async def test_query_fuses_retrieval_and_persists_only_cited_sources() -> None:
    shared, semantic_only, structured_only = uuid4(), uuid4(), uuid4()
    repository = FakeQueryRepository(
        keyword=(hit(shared, QueryType.KEYWORD, "report.pdf"),),
        semantic=(
            hit(semantic_only, QueryType.SEMANTIC, "notes.txt"),
            hit(shared, QueryType.SEMANTIC, "report.pdf"),
        ),
        structured=(hit(structured_only, QueryType.STRUCTURED, "invoice.pdf"),),
    )
    service = CorpusQueryService(
        repository,
        FakeQueryEmbeddings(),
        FakeAnswerGenerator(),
        candidate_limit=5,
        max_sources=3,
    )

    result = await service.query("  How much did Acme grow?  ", user_id=TEST_USER_ID)

    assert result.query == "How much did Acme grow?"
    assert result.query_type is QueryType.HYBRID
    assert result.user_id == TEST_USER_ID
    assert result.answer == "The notes describe the change [2]."
    assert [source.chunk_id for source in result.sources] == [semantic_only]
    assert result.sources[0].citation_number == 2
    assert repository.semantic_request["dimension"] == 3
    assert repository.saved == result


@pytest.mark.asyncio
async def test_document_scope_is_applied_to_every_retriever_and_history() -> None:
    document_id = uuid4()
    repository = FakeQueryRepository((), (), ())
    service = CorpusQueryService(repository, FakeQueryEmbeddings(), FakeAnswerGenerator())

    result = await service.query("What changed?", user_id=TEST_USER_ID, document_id=document_id)

    assert repository.keyword_document_id == document_id
    assert repository.semantic_request["document_id"] == document_id
    assert repository.structured_document_id == document_id
    assert result.document_id == document_id
    assert repository.saved == result


@pytest.mark.asyncio
async def test_empty_query_is_rejected_before_provider_calls() -> None:
    service = CorpusQueryService(
        FakeQueryRepository((), (), ()),
        FakeQueryEmbeddings(),
        FakeAnswerGenerator(),
    )

    with pytest.raises(EmptyQueryError):
        await service.query("   ", user_id=TEST_USER_ID)


@pytest.mark.asyncio
async def test_no_evidence_returns_a_deterministic_answer() -> None:
    repository = FakeQueryRepository((), (), ())
    service = CorpusQueryService(repository, FakeQueryEmbeddings(), FakeAnswerGenerator())

    result = await service.query("What is missing?", user_id=TEST_USER_ID)

    assert result.sources == ()
    assert "couldn't find enough evidence" in result.answer
    assert repository.saved == result
