"""Application-owned embedding provider boundary."""

from typing import Protocol

from app.domain import ChunkVector, ExtractionChunk


class EmbeddingProviderError(RuntimeError):
    """Raised when embeddings cannot be generated or validated."""


class EmbeddingProvider(Protocol):
    provider_name: str
    model_name: str
    model_version: str | None
    dimension: int

    async def embed(self, chunks: tuple[ExtractionChunk, ...]) -> tuple[ChunkVector, ...]: ...

    async def embed_query(self, query: str) -> tuple[float, ...]: ...
