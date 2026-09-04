"""Document-boundary-aware chunk construction with source provenance."""

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4

from app.domain import ElementType, NewCanonicalElement, NewChunk

SECTION_TYPES = frozenset({ElementType.TITLE, ElementType.HEADING})
SKIPPED_TYPES = frozenset({ElementType.HEADER, ElementType.FOOTER, ElementType.IMAGE})


@dataclass(slots=True)
class _ChunkBuffer:
    texts: list[str]
    source_ids: list[UUID]
    pages: list[int]
    section: str | None


def create_chunks(
    elements: tuple[NewCanonicalElement, ...],
    *,
    document_version_id: UUID,
    max_characters: int = 2_000,
) -> tuple[NewChunk, ...]:
    chunks: list[NewChunk] = []
    buffer = _ChunkBuffer(texts=[], source_ids=[], pages=[], section=None)

    def flush() -> None:
        content = "\n\n".join(buffer.texts).strip()
        if not content:
            return
        chunks.append(
            NewChunk(
                id=uuid4(),
                document_version_id=document_version_id,
                ordinal=len(chunks),
                content=content,
                content_hash=hashlib.sha256(content.encode()).hexdigest(),
                section=buffer.section,
                page_start=min(buffer.pages) if buffer.pages else None,
                page_end=max(buffer.pages) if buffer.pages else None,
                source_element_ids=tuple(dict.fromkeys(buffer.source_ids)),
                metadata={"element_count": len(set(buffer.source_ids))},
            )
        )
        buffer.texts.clear()
        buffer.source_ids.clear()
        buffer.pages.clear()

    for element in elements:
        text = (element.text_content or "").strip()
        if not text or element.element_type in SKIPPED_TYPES:
            continue

        if element.element_type in SECTION_TYPES:
            flush()
            buffer.section = text

        parts = _split_text(text, max_characters)
        for part in parts:
            projected = len("\n\n".join([*buffer.texts, part]))
            if buffer.texts and projected > max_characters:
                flush()
            buffer.texts.append(part)
            buffer.source_ids.append(element.id)
            if element.page_number is not None:
                buffer.pages.append(element.page_number)
            if element.element_type == ElementType.TABLE:
                flush()

    flush()
    return tuple(chunks)


def _split_text(text: str, max_characters: int) -> tuple[str, ...]:
    if max_characters < 1:
        raise ValueError("max_characters must be positive")
    if len(text) <= max_characters:
        return (text,)

    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_characters:
            parts.append(remaining)
            break
        split_at = remaining.rfind(" ", 0, max_characters + 1)
        if split_at < 1:
            split_at = max_characters
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    return tuple(part for part in parts if part)
