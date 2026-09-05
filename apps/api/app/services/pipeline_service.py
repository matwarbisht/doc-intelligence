"""Composition root for the complete document processing pipeline."""

import asyncio
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.services.enrichment_service import DocumentEnrichmentService
from app.services.processing_service import DocumentProcessingService, ProcessingResult


@runtime_checkable
class DocumentProcessor(Protocol):
    async def process_document(self, document_id: UUID) -> ProcessingResult: ...


class BoundedDocumentProcessor:
    """Limit concurrent pipelines before provider cost remains predictable."""

    def __init__(self, processor: DocumentProcessor, *, max_concurrency: int) -> None:
        self._processor = processor
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def process_document(self, document_id: UUID) -> ProcessingResult:
        async with self._semaphore:
            return await self._processor.process_document(document_id)


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
