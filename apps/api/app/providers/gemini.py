"""Gemini adapters for structured extraction and document embeddings."""

import asyncio
import json
import math
from collections.abc import Mapping
from typing import cast

import httpx
from pydantic import ValidationError

from app.domain import ChunkVector, ExtractionChunk, SemanticExtraction
from app.providers.embedding_provider import EmbeddingProviderError
from app.providers.semantic_extractor import SemanticExtractionError

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _gemini_http_error(operation: str, error: httpx.HTTPError) -> str:
    status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
    detail = f" with status {status}" if status is not None else ""
    return f"Gemini {operation} failed{detail}."


class GeminiSemanticExtractor:
    provider_name = "gemini"
    model_version: str | None = None
    prompt_version = "semantic-extraction-v1"
    schema_version = "semantic-intelligence-v1"

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        timeout_seconds: float = 120,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self.model_name = model_name
        self._timeout_seconds = timeout_seconds

    async def extract(self, chunks: tuple[ExtractionChunk, ...]) -> SemanticExtraction:
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": self._prompt(chunks)}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": SemanticExtraction.model_json_schema(),
            },
        }
        try:
            response = await self._client.post(
                f"{GEMINI_API_BASE_URL}/models/{self.model_name}:generateContent",
                headers={"x-goog-api-key": self._api_key},
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise SemanticExtractionError(_gemini_http_error("extraction", error)) from error

        try:
            body = cast(Mapping[object, object], response.json())
            candidates = cast(list[object], body["candidates"])
            candidate = cast(Mapping[object, object], candidates[0])
            content = cast(Mapping[object, object], candidate["content"])
            parts = cast(list[object], content["parts"])
            part = cast(Mapping[object, object], parts[0])
            text = cast(str, part["text"])
            return SemanticExtraction.model_validate_json(text)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as error:
            raise SemanticExtractionError("Gemini returned invalid extraction output.") from error

    def _prompt(self, chunks: tuple[ExtractionChunk, ...]) -> str:
        records = [{"source_chunk_id": str(chunk.id), "content": chunk.content} for chunk in chunks]
        return (
            "Extract a lightweight, domain-independent semantic representation from the "
            "document chunks below. Use only the supplied text. Every mention, fact, and "
            "relationship must cite one exact source_chunk_id from the input. Keep the "
            "summary concise, topics distinct, predicates in snake_case, confidence between "
            "0 and 1, and do not invent unsupported information.\n\n"
            + json.dumps(records, ensure_ascii=False)
        )


class GeminiEmbeddingProvider:
    provider_name = "gemini"
    model_version: str | None = None

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        api_key: str,
        model_name: str = "gemini-embedding-001",
        dimension: int = 768,
        timeout_seconds: float = 60,
        concurrency: int = 5,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self.model_name = model_name
        self.dimension = dimension
        self._timeout_seconds = timeout_seconds
        self._semaphore = asyncio.Semaphore(concurrency)

    async def embed(self, chunks: tuple[ExtractionChunk, ...]) -> tuple[ChunkVector, ...]:
        return tuple(await asyncio.gather(*(self._embed_one(chunk) for chunk in chunks)))

    async def _embed_one(self, chunk: ExtractionChunk) -> ChunkVector:
        async with self._semaphore:
            try:
                response = await self._client.post(
                    f"{GEMINI_API_BASE_URL}/models/{self.model_name}:embedContent",
                    headers={"x-goog-api-key": self._api_key},
                    json={
                        "content": {"parts": [{"text": chunk.content}]},
                        "taskType": "RETRIEVAL_DOCUMENT",
                        "outputDimensionality": self.dimension,
                    },
                    timeout=self._timeout_seconds,
                )
                response.raise_for_status()
            except httpx.HTTPError as error:
                raise EmbeddingProviderError(_gemini_http_error("embedding", error)) from error
        try:
            payload = cast(Mapping[object, object], response.json())
            embedding = cast(Mapping[object, object], payload["embedding"])
            raw_values = cast(list[object], embedding["values"])
            if not all(isinstance(value, int | float) for value in raw_values):
                raise TypeError
            values = tuple(float(cast(int | float, value)) for value in raw_values)
        except (KeyError, TypeError, ValueError) as error:
            raise EmbeddingProviderError("Gemini returned an invalid embedding.") from error
        if len(values) != self.dimension or not all(math.isfinite(value) for value in values):
            raise EmbeddingProviderError("Gemini returned an invalid embedding dimension.")
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            raise EmbeddingProviderError("Gemini returned an empty embedding vector.")
        return ChunkVector(chunk_id=chunk.id, values=tuple(value / norm for value in values))
