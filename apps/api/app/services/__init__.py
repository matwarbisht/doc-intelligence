"""Application use-case services."""

from app.services.authentication_service import AuthenticationService, SuspendedAccountError
from app.services.document_service import (
    DocumentService,
    DocumentUpload,
    DocumentUploadError,
    EmptyDocumentError,
    FileTooLargeError,
    UnsupportedDocumentTypeError,
)
from app.services.enrichment_service import DocumentEnrichmentService, EnrichmentResult
from app.services.pipeline_service import (
    BoundedDocumentProcessor,
    DocumentPipelineService,
    DocumentProcessor,
)
from app.services.processing_service import (
    DocumentProcessingService,
    ProcessingError,
    ProcessingResult,
)
from app.services.query_service import CorpusQueryService, EmptyQueryError, QueryServiceError
from app.services.safeguard_service import (
    Capabilities,
    LogAlertSink,
    SafeguardLimits,
    SafeguardService,
    SafeguardViolation,
)

__all__ = [
    "AuthenticationService",
    "CorpusQueryService",
    "Capabilities",
    "BoundedDocumentProcessor",
    "DocumentService",
    "DocumentProcessingService",
    "DocumentEnrichmentService",
    "DocumentPipelineService",
    "DocumentProcessor",
    "DocumentUpload",
    "DocumentUploadError",
    "EmptyDocumentError",
    "EmptyQueryError",
    "EnrichmentResult",
    "FileTooLargeError",
    "ProcessingError",
    "ProcessingResult",
    "QueryServiceError",
    "LogAlertSink",
    "SafeguardLimits",
    "SafeguardService",
    "SafeguardViolation",
    "SuspendedAccountError",
    "UnsupportedDocumentTypeError",
]
