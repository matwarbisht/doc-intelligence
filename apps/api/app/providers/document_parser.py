"""Application-owned document parser boundary."""

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from app.domain import Metadata, StructuredContent


class DocumentParserError(RuntimeError):
    """Raised when a parsing provider cannot produce a valid document."""


@dataclass(frozen=True, slots=True)
class ParsedElement:
    provider_id: str
    category: str
    text: str | None = None
    page_number: int | None = None
    parent_provider_id: str | None = None
    structured_content: StructuredContent | None = None
    metadata: Metadata = field(default_factory=dict[str, object])


@dataclass(frozen=True, slots=True)
class ParsedDocument:
    elements: tuple[ParsedElement, ...]


class DocumentParser(Protocol):
    provider_name: str
    provider_version: str

    async def parse(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
        user_id: UUID | None = None,
    ) -> ParsedDocument: ...
