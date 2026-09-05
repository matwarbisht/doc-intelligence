"""Application-owned semantic extraction provider boundary."""

from typing import Protocol
from uuid import UUID

from app.domain import ExtractionChunk, SemanticExtraction


class SemanticExtractionError(RuntimeError):
    """Raised when semantic extraction cannot return validated output."""


class SemanticExtractor(Protocol):
    provider_name: str
    model_name: str
    model_version: str | None
    prompt_version: str
    schema_version: str

    async def extract(
        self,
        chunks: tuple[ExtractionChunk, ...],
        *,
        user_id: UUID | None = None,
    ) -> SemanticExtraction: ...
