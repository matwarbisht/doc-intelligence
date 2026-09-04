from uuid import uuid4

from app.domain import ElementType
from app.providers import ParsedDocument, ParsedElement
from app.services.canonicalization import canonicalize_document
from app.services.chunking import create_chunks


def test_canonicalization_preserves_structure_and_table_data() -> None:
    version_id = uuid4()
    parsed = ParsedDocument(
        elements=(
            ParsedElement(provider_id="h1", category="Title", text="Quarterly results"),
            ParsedElement(
                provider_id="t1",
                category="Table",
                text="Revenue 24%",
                page_number=2,
                parent_provider_id="h1",
                structured_content={"html": "<table></table>"},
            ),
        )
    )

    elements = canonicalize_document(parsed, document_version_id=version_id)

    assert elements[0].element_type == ElementType.TITLE
    assert elements[1].element_type == ElementType.TABLE
    assert elements[1].parent_element_id == elements[0].id
    assert elements[1].structured_content == {"html": "<table></table>"}
    assert elements[1].metadata["provider_element_id"] == "t1"


def test_chunking_uses_sections_and_preserves_page_and_element_provenance() -> None:
    version_id = uuid4()
    parsed = ParsedDocument(
        elements=(
            ParsedElement(provider_id="h1", category="Title", text="Results", page_number=1),
            ParsedElement(
                provider_id="p1",
                category="NarrativeText",
                text="Revenue increased by 24 percent.",
                page_number=2,
                parent_provider_id="h1",
            ),
            ParsedElement(provider_id="h2", category="Title", text="Outlook", page_number=3),
            ParsedElement(
                provider_id="p2",
                category="NarrativeText",
                text="Demand remains strong.",
                page_number=3,
                parent_provider_id="h2",
            ),
        )
    )
    elements = canonicalize_document(parsed, document_version_id=version_id)

    chunks = create_chunks(elements, document_version_id=version_id)

    assert [chunk.section for chunk in chunks] == ["Results", "Outlook"]
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 2
    assert chunks[0].source_element_ids == (elements[0].id, elements[1].id)
    assert chunks[1].source_element_ids == (elements[2].id, elements[3].id)


def test_chunking_splits_oversized_elements_at_word_boundaries() -> None:
    version_id = uuid4()
    elements = canonicalize_document(
        ParsedDocument(
            elements=(
                ParsedElement(
                    provider_id="p1",
                    category="NarrativeText",
                    text="one two three four five",
                    page_number=1,
                ),
            )
        ),
        document_version_id=version_id,
    )

    chunks = create_chunks(elements, document_version_id=version_id, max_characters=10)

    assert [chunk.content for chunk in chunks] == ["one two", "three four", "five"]
    assert all(chunk.source_element_ids == (elements[0].id,) for chunk in chunks)
