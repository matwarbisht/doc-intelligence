# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_query_service
from app.api.routes.queries import router
from app.domain import QueryResult, QueryType, RetrievalHit


class StubQueryService:
    async def query(self, question: str) -> QueryResult:
        return QueryResult(
            id=uuid4(),
            query=question,
            query_type=QueryType.HYBRID,
            answer="Revenue grew by 24% [1].",
            sources=(
                RetrievalHit(
                    chunk_id=uuid4(),
                    document_id=uuid4(),
                    filename="report.pdf",
                    content="Revenue grew by 24%.",
                    page_start=7,
                    page_end=7,
                    score=0.03,
                    match_types=(QueryType.KEYWORD, QueryType.SEMANTIC),
                ),
            ),
            created_at=datetime.now(UTC),
        )


def test_query_endpoint_returns_answer_and_source_provenance() -> None:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_query_service] = lambda: StubQueryService()
    client = TestClient(application)

    try:
        response = client.post("/api/v1/query", json={"query": "How much did revenue grow?"})
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_type"] == "hybrid"
    assert payload["answer"] == "Revenue grew by 24% [1]."
    assert payload["sources"][0] == {
        "citation_number": 1,
        "document_id": payload["sources"][0]["document_id"],
        "chunk_id": payload["sources"][0]["chunk_id"],
        "filename": "report.pdf",
        "section": None,
        "page_start": 7,
        "page_end": 7,
        "excerpt": "Revenue grew by 24%.",
        "score": 0.03,
        "match_types": ["keyword", "semantic"],
    }


def test_query_endpoint_requires_configuration() -> None:
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    client = TestClient(application)

    try:
        response = client.post("/api/v1/query", json={"query": "What happened?"})
    finally:
        client.close()

    assert response.status_code == 503
    assert response.json() == {"detail": "Corpus querying is not configured."}
