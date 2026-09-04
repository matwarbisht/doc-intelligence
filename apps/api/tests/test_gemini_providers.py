import json

# pyright: reportUnknownMemberType=false
from uuid import uuid4

import httpx
import pytest

from app.domain import ExtractionChunk, RetrievalHit
from app.providers import GeminiAnswerGenerator, GeminiEmbeddingProvider, GeminiSemanticExtractor


@pytest.mark.asyncio
async def test_gemini_extractor_requests_and_validates_structured_output() -> None:
    chunk_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/gemini-test:generateContent")
        assert request.headers["x-goog-api-key"] == "test-key"
        body = json.loads(request.content)
        assert body["generationConfig"]["responseMimeType"] == "application/json"
        assert str(chunk_id) in body["contents"][0]["parts"][0]["text"]
        extraction = {
            "document_type": "financial_report",
            "summary": "Acme grew revenue.",
            "topics": ["revenue"],
            "entities": [
                {
                    "name": "Acme",
                    "entity_type": "organization",
                    "mentions": [
                        {
                            "source_chunk_id": str(chunk_id),
                            "surface_text": "Acme",
                            "confidence": 0.9,
                        }
                    ],
                }
            ],
            "facts": [],
            "relationships": [],
        }
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(extraction)}]}}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        extractor = GeminiSemanticExtractor(client, api_key="test-key", model_name="gemini-test")
        result = await extractor.extract(
            (ExtractionChunk(id=chunk_id, content="Acme grew revenue."),)
        )

    assert result.summary == "Acme grew revenue."
    assert result.entities[0].mentions[0].source_chunk_id == chunk_id


@pytest.mark.asyncio
async def test_gemini_embeddings_are_dimension_checked_and_normalized() -> None:
    first_id, second_id = uuid4(), uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["taskType"] == "RETRIEVAL_DOCUMENT"
        assert body["outputDimensionality"] == 3
        return httpx.Response(200, json={"embedding": {"values": [3, 4, 0]}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiEmbeddingProvider(
            client,
            api_key="test-key",
            model_name="embedding-test",
            dimension=3,
        )
        vectors = await provider.embed(
            (
                ExtractionChunk(id=first_id, content="One"),
                ExtractionChunk(id=second_id, content="Two"),
            )
        )

    assert [vector.chunk_id for vector in vectors] == [first_id, second_id]
    assert vectors[0].values == pytest.approx((0.6, 0.8, 0))


@pytest.mark.asyncio
async def test_gemini_uses_retrieval_query_task_type() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["taskType"] == "RETRIEVAL_QUERY"
        return httpx.Response(200, json={"embedding": {"values": [1, 0, 0]}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GeminiEmbeddingProvider(client, api_key="test", dimension=3)
        vector = await provider.embed_query("revenue growth")

    assert vector == (1.0, 0.0, 0.0)


@pytest.mark.asyncio
async def test_gemini_answer_generator_validates_cited_evidence() -> None:
    chunk_id = uuid4()

    async def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert str(chunk_id) in body["contents"][0]["parts"][0]["text"]
        assert "untrusted evidence" in body["systemInstruction"]["parts"][0]["text"]
        answer = {
            "answer": "Revenue grew by 24% [1].",
            "citations": [{"source_number": 1, "chunk_id": str(chunk_id)}],
        }
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]},
        )

    evidence = RetrievalHit(
        chunk_id=chunk_id,
        document_id=uuid4(),
        filename="report.pdf",
        content="Revenue grew by 24%.",
        score=1,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        generator = GeminiAnswerGenerator(client, api_key="test", model_name="answer-test")
        result = await generator.generate("How much?", (evidence,))

    assert result.answer == "Revenue grew by 24% [1]."
    assert result.citations[0].chunk_id == chunk_id
