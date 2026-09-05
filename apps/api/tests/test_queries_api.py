# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_current_user,
    get_document_service,
    get_query_service,
    get_safeguard_service,
)
from app.api.routes.queries import router
from app.domain import (
    AuthenticatedUser,
    Document,
    DocumentStatus,
    QueryResult,
    QueryType,
    RetrievalHit,
)
from app.services import DocumentService
from tests.fakes import (
    InMemoryDocumentRepository,
    InMemoryObjectStorage,
    unrestricted_safeguards,
)

TEST_USER = AuthenticatedUser(
    id=UUID("10000000-0000-4000-8000-000000000001"), email="alice@example.test"
)
OTHER_USER_ID = UUID("20000000-0000-4000-8000-000000000002")


class StubQueryService:
    document_id: UUID | None = None

    async def query(
        self,
        question: str,
        *,
        user_id: UUID,
        document_id: UUID | None = None,
    ) -> QueryResult:
        self.document_id = document_id
        return QueryResult(
            id=uuid4(),
            user_id=user_id,
            query=question,
            query_type=QueryType.HYBRID,
            document_id=document_id,
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
    application.dependency_overrides[get_document_service] = lambda: DocumentService(
        InMemoryDocumentRepository(), InMemoryObjectStorage()
    )
    application.dependency_overrides[get_current_user] = lambda: TEST_USER
    application.dependency_overrides[get_safeguard_service] = unrestricted_safeguards
    client = TestClient(application)

    try:
        response = client.post("/api/v1/query", json={"query": "How much did revenue grow?"})
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["query_type"] == "hybrid"
    assert payload["document_id"] is None
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
    application.dependency_overrides[get_document_service] = lambda: DocumentService(
        InMemoryDocumentRepository(), InMemoryObjectStorage()
    )
    application.dependency_overrides[get_current_user] = lambda: TEST_USER
    application.dependency_overrides[get_safeguard_service] = unrestricted_safeguards
    client = TestClient(application)

    try:
        response = client.post("/api/v1/query", json={"query": "What happened?"})
    finally:
        client.close()

    assert response.status_code == 503
    assert response.json() == {"detail": "Corpus querying is not configured."}


def test_query_endpoint_forwards_document_scope() -> None:
    service = StubQueryService()
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_query_service] = lambda: service
    repository = InMemoryDocumentRepository()
    document_service = DocumentService(repository, InMemoryObjectStorage())
    application.dependency_overrides[get_document_service] = lambda: document_service
    application.dependency_overrides[get_current_user] = lambda: TEST_USER
    application.dependency_overrides[get_safeguard_service] = unrestricted_safeguards
    client = TestClient(application)
    document_id = uuid4()
    now = datetime.now(UTC)
    repository.documents[document_id] = Document(
        owner_id=TEST_USER.id,
        id=document_id,
        filename="scope.txt",
        mime_type="text/plain",
        storage_path="test/scope.txt",
        content_hash="scope",
        status=DocumentStatus.READY,
        created_at=now,
        updated_at=now,
    )

    try:
        response = client.post(
            "/api/v1/query",
            json={"query": "What changed?", "document_id": str(document_id)},
        )
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["document_id"] == str(document_id)
    assert service.document_id == document_id


def test_query_endpoint_rejects_another_users_document_scope() -> None:
    service = StubQueryService()
    repository = InMemoryDocumentRepository()
    document_service = DocumentService(repository, InMemoryObjectStorage())
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_query_service] = lambda: service
    application.dependency_overrides[get_document_service] = lambda: document_service
    application.dependency_overrides[get_current_user] = lambda: TEST_USER
    application.dependency_overrides[get_safeguard_service] = unrestricted_safeguards
    document_id = uuid4()
    now = datetime.now(UTC)
    repository.documents[document_id] = Document(
        owner_id=OTHER_USER_ID,
        id=document_id,
        filename="private.txt",
        mime_type="text/plain",
        storage_path="test/private.txt",
        content_hash="private",
        status=DocumentStatus.READY,
        created_at=now,
        updated_at=now,
    )
    client = TestClient(application)

    try:
        response = client.post(
            "/api/v1/query",
            json={"query": "What is private?", "document_id": str(document_id)},
        )
    finally:
        client.close()
        application.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found."}
    assert service.document_id is None
