"""Application use-case services."""

from app.services.document_service import (
    DocumentService,
    DocumentUpload,
    DocumentUploadError,
    EmptyDocumentError,
    FileTooLargeError,
    UnsupportedDocumentTypeError,
)
from app.services.enrichment_service import DocumentEnrichmentService, EnrichmentResult
from app.services.pipeline_service import DocumentPipelineService
from app.services.processing_service import (
    DocumentProcessingService,
    ProcessingError,
    ProcessingResult,
)
from app.services.query_service import CorpusQueryService, EmptyQueryError, QueryServiceError

__all__ = [
    "CorpusQueryService",
    "DocumentService",
    "DocumentProcessingService",
    "DocumentEnrichmentService",
    "DocumentPipelineService",
    "DocumentUpload",
    "DocumentUploadError",
    "EmptyDocumentError",
    "EmptyQueryError",
    "EnrichmentResult",
    "FileTooLargeError",
    "ProcessingError",
    "ProcessingResult",
    "QueryServiceError",
    "UnsupportedDocumentTypeError",
]
