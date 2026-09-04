"""Persistence boundary for parsing jobs and canonical output."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain import (
    Document,
    DocumentVersion,
    NewCanonicalElement,
    NewChunk,
    ProcessingJob,
)


@dataclass(frozen=True, slots=True)
class ParsingClaim:
    document: Document
    version: DocumentVersion
    job: ProcessingJob


class ProcessingRepository(Protocol):
    async def claim_parsing(
        self,
        document_id: UUID,
        *,
        max_attempts: int,
        stale_after_seconds: int,
    ) -> ParsingClaim | None: ...

    async def complete_parsing(
        self,
        claim: ParsingClaim,
        *,
        parser_provider: str,
        parser_version: str,
        elements: tuple[NewCanonicalElement, ...],
        chunks: tuple[NewChunk, ...],
    ) -> Document: ...

    async def fail_parsing(self, claim: ParsingClaim, *, error: str) -> Document: ...
