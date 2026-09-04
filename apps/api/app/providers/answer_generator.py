"""Application-owned boundary for grounded answer generation."""

from typing import Protocol

from app.domain import GeneratedAnswer, RetrievalHit


class AnswerGeneratorError(RuntimeError):
    """Raised when an answer provider cannot return a valid grounded answer."""


class AnswerGenerator(Protocol):
    provider_name: str
    model_name: str
    model_version: str | None
    prompt_version: str
    schema_version: str

    async def generate(
        self,
        question: str,
        evidence: tuple[RetrievalHit, ...],
    ) -> GeneratedAnswer: ...
