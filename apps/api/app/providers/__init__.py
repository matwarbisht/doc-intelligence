"""External provider interfaces and adapters."""

from app.providers.document_parser import (
    DocumentParser,
    DocumentParserError,
    ParsedDocument,
    ParsedElement,
)
from app.providers.embedding_provider import EmbeddingProvider, EmbeddingProviderError
from app.providers.gemini import GeminiEmbeddingProvider, GeminiSemanticExtractor
from app.providers.object_storage import ObjectStorage, ObjectStorageError
from app.providers.semantic_extractor import SemanticExtractionError, SemanticExtractor
from app.providers.supabase_storage import SupabaseObjectStorage
from app.providers.unstructured_parser import UnstructuredDocumentParser

__all__ = [
    "DocumentParser",
    "DocumentParserError",
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "GeminiEmbeddingProvider",
    "GeminiSemanticExtractor",
    "ObjectStorage",
    "ObjectStorageError",
    "ParsedDocument",
    "ParsedElement",
    "SupabaseObjectStorage",
    "SemanticExtractionError",
    "SemanticExtractor",
    "UnstructuredDocumentParser",
]
