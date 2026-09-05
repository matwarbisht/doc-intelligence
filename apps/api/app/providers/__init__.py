"""External provider interfaces and adapters."""

from app.providers.answer_generator import AnswerGenerator, AnswerGeneratorError
from app.providers.auth_provider import (
    AuthenticationProvider,
    AuthenticationUnavailableError,
    InvalidAccessTokenError,
)
from app.providers.document_parser import (
    DocumentParser,
    DocumentParserError,
    ParsedDocument,
    ParsedElement,
)
from app.providers.embedding_provider import EmbeddingProvider, EmbeddingProviderError
from app.providers.gemini import (
    GeminiAnswerGenerator,
    GeminiEmbeddingProvider,
    GeminiSemanticExtractor,
)
from app.providers.object_storage import ObjectStorage, ObjectStorageError
from app.providers.semantic_extractor import SemanticExtractionError, SemanticExtractor
from app.providers.supabase_auth import SupabaseAuthenticationProvider
from app.providers.supabase_storage import SupabaseObjectStorage
from app.providers.unstructured_parser import UnstructuredDocumentParser

__all__ = [
    "AnswerGenerator",
    "AnswerGeneratorError",
    "AuthenticationProvider",
    "AuthenticationUnavailableError",
    "DocumentParser",
    "DocumentParserError",
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "GeminiAnswerGenerator",
    "GeminiEmbeddingProvider",
    "GeminiSemanticExtractor",
    "InvalidAccessTokenError",
    "ObjectStorage",
    "ObjectStorageError",
    "ParsedDocument",
    "ParsedElement",
    "SupabaseObjectStorage",
    "SupabaseAuthenticationProvider",
    "SemanticExtractionError",
    "SemanticExtractor",
    "UnstructuredDocumentParser",
]
