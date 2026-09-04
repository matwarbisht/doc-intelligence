"""Composition root for the complete document processing pipeline."""

from uuid import UUID

from app.services.enrichment_service import DocumentEnrichmentService
from app.services.processing_service import DocumentProcessingService, ProcessingResult


class DocumentPipelineService:
    def __init__(
        self,
        parsing: DocumentProcessingService,
        enrichment: DocumentEnrichmentService,
    ) -> None:
        self._parsing = parsing
        self._enrichment = enrichment

    async def process_document(self, document_id: UUID) -> ProcessingResult:
        parsing = await self._parsing.process_document(document_id)
        if parsing.document is not None and parsing.document.status.value.endswith("_failed"):
            return parsing
        enrichment = await self._enrichment.process_document(document_id)
        return ProcessingResult(
            claimed=parsing.claimed or enrichment.claimed,
            document=enrichment.document or parsing.document,
        )
