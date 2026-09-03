from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain import (
    Chunk,
    ChunkEmbedding,
    NewDocument,
    Relationship,
)


def test_new_document_has_safe_defaults() -> None:
    document = NewDocument(
        filename="report.pdf",
        mime_type="application/pdf",
        storage_path="documents/report.pdf",
        content_hash="sha256:abc123",
    )

    assert document.metadata == {}
    assert document.filename == "report.pdf"


def test_chunk_rejects_inverted_page_range() -> None:
    with pytest.raises(ValidationError, match="page_end"):
        Chunk(
            id=uuid4(),
            document_version_id=uuid4(),
            ordinal=0,
            content="Evidence",
            content_hash="sha256:evidence",
            page_start=4,
            page_end=3,
            created_at=datetime.now(UTC),
        )


def test_embedding_dimension_must_match_values() -> None:
    with pytest.raises(ValidationError, match="dimension"):
        ChunkEmbedding(
            id=uuid4(),
            chunk_id=uuid4(),
            provider="example",
            model_name="embedding-model",
            dimension=3,
            embedding=(0.1, 0.2),
            created_at=datetime.now(UTC),
        )


def test_relationship_requires_exactly_one_object() -> None:
    with pytest.raises(ValidationError, match="exactly one"):
        Relationship(
            id=uuid4(),
            extraction_run_id=uuid4(),
            source_chunk_id=uuid4(),
            subject_entity_id=uuid4(),
            predicate="works_for",
            created_at=datetime.now(UTC),
        )

    relationship = Relationship(
        id=uuid4(),
        extraction_run_id=uuid4(),
        source_chunk_id=uuid4(),
        subject_entity_id=uuid4(),
        predicate="works_for",
        object_text="Example Corp",
        created_at=datetime.now(UTC),
    )
    assert relationship.object_text == "Example Corp"
