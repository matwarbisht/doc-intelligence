"""Provider-independent canonicalization of parsed document elements."""

from uuid import UUID, uuid4

from app.domain import ElementType, NewCanonicalElement
from app.providers import ParsedDocument

ELEMENT_TYPES = {
    "title": ElementType.TITLE,
    "heading": ElementType.HEADING,
    "paragraph": ElementType.PARAGRAPH,
    "text": ElementType.PARAGRAPH,
    "narrativetext": ElementType.NARRATIVE_TEXT,
    "list": ElementType.LIST,
    "listitem": ElementType.LIST_ITEM,
    "table": ElementType.TABLE,
    "image": ElementType.IMAGE,
    "figurecaption": ElementType.CAPTION,
    "caption": ElementType.CAPTION,
    "footer": ElementType.FOOTER,
    "header": ElementType.HEADER,
}


def canonicalize_document(
    parsed: ParsedDocument,
    *,
    document_version_id: UUID,
) -> tuple[NewCanonicalElement, ...]:
    generated_ids = [uuid4() for _element in parsed.elements]
    element_ids: dict[str, UUID] = {}
    for element, generated_id in zip(parsed.elements, generated_ids, strict=True):
        element_ids.setdefault(element.provider_id, generated_id)
    canonical: list[NewCanonicalElement] = []

    for ordinal, (element, generated_id) in enumerate(
        zip(parsed.elements, generated_ids, strict=True)
    ):
        metadata = {
            **element.metadata,
            "provider_element_id": element.provider_id,
            "provider_element_type": element.category,
        }
        canonical.append(
            NewCanonicalElement(
                id=generated_id,
                document_version_id=document_version_id,
                ordinal=ordinal,
                element_type=ELEMENT_TYPES.get(
                    element.category.replace("_", "").replace(" ", "").lower(),
                    ElementType.UNKNOWN,
                ),
                parent_element_id=(
                    element_ids.get(element.parent_provider_id)
                    if element.parent_provider_id
                    else None
                ),
                text_content=element.text,
                page_number=element.page_number,
                structured_content=element.structured_content,
                metadata=metadata,
            )
        )

    return tuple(canonical)
