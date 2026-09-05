import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import safeguard_violation_handler
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, log_request
from app.db import create_database_pool
from app.providers import (
    GeminiAnswerGenerator,
    GeminiEmbeddingProvider,
    GeminiSemanticExtractor,
    SupabaseAuthenticationProvider,
    SupabaseObjectStorage,
    UnstructuredDocumentParser,
)
from app.repositories import (
    PostgresDocumentRepository,
    PostgresEnrichmentRepository,
    PostgresProcessingRepository,
    PostgresProfileRepository,
    PostgresQueryRepository,
    PostgresSafeguardRepository,
)
from app.services import (
    AuthenticationService,
    BoundedDocumentProcessor,
    Capabilities,
    CorpusQueryService,
    DocumentEnrichmentService,
    DocumentPipelineService,
    DocumentProcessingService,
    DocumentProcessor,
    DocumentService,
    SafeguardLimits,
    SafeguardService,
    SafeguardViolation,
)

settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.log_format == "json")
LOCAL_CORS_ORIGIN_REGEX = r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$"
logger = logging.getLogger(__name__)


def api_documentation_paths(app_env: str) -> tuple[str | None, str | None]:
    if app_env == "development":
        return "/docs", "/openapi.json"
    return None, None


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
    application.state.authentication_service = None
    application.state.document_service = None
    application.state.processing_service = None
    application.state.query_service = None
    application.state.safeguard_service = None
    if settings.database_url and settings.supabase_url and settings.supabase_service_role_key:
        pool = await create_database_pool(settings.database_url)
        async with httpx.AsyncClient(timeout=30) as client:
            safeguard_service = SafeguardService(
                PostgresSafeguardRepository(pool),
                capabilities=Capabilities(
                    public_signup=settings.public_signup_enabled,
                    uploads=settings.uploads_enabled,
                    processing=settings.processing_enabled,
                    processing_retries=settings.processing_retries_enabled,
                    ask=settings.ask_enabled,
                ),
                limits=SafeguardLimits(
                    user_uploads_per_hour=settings.user_uploads_per_hour,
                    user_documents_per_day=settings.user_documents_per_day,
                    user_upload_bytes_per_day=settings.user_upload_bytes_per_day,
                    user_asks_per_hour=settings.user_asks_per_hour,
                    user_asks_per_day=settings.user_asks_per_day,
                    user_retries_per_hour=settings.user_retries_per_hour,
                    user_retries_per_day=settings.user_retries_per_day,
                    user_max_documents=settings.user_max_documents,
                    retry_cooldown_seconds=settings.retry_cooldown_seconds,
                    ip_uploads_per_hour=settings.ip_uploads_per_hour,
                    ip_asks_per_hour=settings.ip_asks_per_hour,
                    global_documents_per_day=settings.global_documents_per_day,
                    global_upload_bytes_per_day=settings.global_upload_bytes_per_day,
                    global_asks_per_day=settings.global_asks_per_day,
                    user_unstructured_attempts_per_day=(
                        settings.user_unstructured_attempts_per_day
                    ),
                    global_unstructured_attempts_per_day=(
                        settings.global_unstructured_attempts_per_day
                    ),
                    user_gemini_extractions_per_day=(settings.user_gemini_extractions_per_day),
                    global_gemini_extractions_per_day=(settings.global_gemini_extractions_per_day),
                    user_gemini_embedding_calls_per_day=(
                        settings.user_gemini_embedding_calls_per_day
                    ),
                    global_gemini_embedding_calls_per_day=(
                        settings.global_gemini_embedding_calls_per_day
                    ),
                    user_gemini_query_embeddings_per_day=(
                        settings.user_gemini_query_embeddings_per_day
                    ),
                    global_gemini_query_embeddings_per_day=(
                        settings.global_gemini_query_embeddings_per_day
                    ),
                    user_gemini_answers_per_day=settings.user_gemini_answers_per_day,
                    global_gemini_answers_per_day=settings.global_gemini_answers_per_day,
                    provider_circuit_failure_threshold=(
                        settings.provider_circuit_failure_threshold
                    ),
                    provider_circuit_window_seconds=(settings.provider_circuit_window_seconds),
                    provider_circuit_cooldown_seconds=(settings.provider_circuit_cooldown_seconds),
                ),
                ip_hash_salt=settings.ip_hash_salt,
            )
            application.state.safeguard_service = safeguard_service
            for operation, enabled in {
                "public_signup": settings.public_signup_enabled,
                "uploads": settings.uploads_enabled,
                "processing": settings.processing_enabled,
                "processing_retries": settings.processing_retries_enabled,
                "ask": settings.ask_enabled,
            }.items():
                if not enabled:
                    logger.warning(
                        "Application capability is disabled",
                        extra={
                            "event": "safeguard.capability.disabled",
                            "operation": operation,
                        },
                    )
            if settings.supabase_publishable_key:
                application.state.authentication_service = AuthenticationService(
                    SupabaseAuthenticationProvider(
                        client,
                        supabase_url=settings.supabase_url,
                        publishable_key=settings.supabase_publishable_key,
                    ),
                    PostgresProfileRepository(pool),
                )
            storage = SupabaseObjectStorage(
                client,
                supabase_url=settings.supabase_url,
                service_role_key=settings.supabase_service_role_key,
                bucket=settings.supabase_storage_bucket,
            )
            application.state.document_service = DocumentService(
                PostgresDocumentRepository(pool),
                storage,
                max_upload_bytes=settings.max_upload_bytes,
            )
            embedding_provider = None
            if settings.gemini_api_key:
                embedding_provider = GeminiEmbeddingProvider(
                    client,
                    api_key=settings.gemini_api_key,
                    model_name=settings.gemini_embedding_model,
                    dimension=settings.gemini_embedding_dimension,
                    timeout_seconds=settings.gemini_timeout_seconds,
                    concurrency=settings.gemini_embedding_concurrency,
                    max_attempts=settings.gemini_max_attempts,
                    retry_base_seconds=settings.gemini_retry_base_seconds,
                    usage_guard=safeguard_service,
                )
                application.state.query_service = CorpusQueryService(
                    PostgresQueryRepository(pool),
                    embedding_provider,
                    GeminiAnswerGenerator(
                        client,
                        api_key=settings.gemini_api_key,
                        model_name=settings.gemini_answer_model,
                        timeout_seconds=settings.gemini_timeout_seconds,
                        max_attempts=settings.gemini_max_attempts,
                        retry_base_seconds=settings.gemini_retry_base_seconds,
                        usage_guard=safeguard_service,
                    ),
                    candidate_limit=settings.retrieval_candidate_limit,
                    max_sources=settings.retrieval_max_sources,
                )
            if settings.unstructured_api_url and settings.unstructured_api_key:
                parser = UnstructuredDocumentParser(
                    client,
                    api_url=settings.unstructured_api_url,
                    api_key=settings.unstructured_api_key,
                    template_id=settings.unstructured_template_id,
                    timeout_seconds=settings.unstructured_timeout_seconds,
                    poll_interval_seconds=settings.unstructured_poll_interval_seconds,
                    concurrency=settings.unstructured_concurrency,
                    max_attempts=settings.unstructured_max_attempts,
                    retry_base_seconds=settings.unstructured_retry_base_seconds,
                    usage_guard=safeguard_service,
                )
                parsing_service = DocumentProcessingService(
                    PostgresProcessingRepository(pool),
                    storage,
                    parser,
                    max_attempts=settings.processing_max_attempts,
                    stale_after_seconds=settings.processing_stale_after_seconds,
                    max_chunk_characters=settings.max_chunk_characters,
                )
                processor: DocumentProcessor = parsing_service
                if settings.gemini_api_key and embedding_provider is not None:
                    enrichment_service = DocumentEnrichmentService(
                        PostgresEnrichmentRepository(pool),
                        GeminiSemanticExtractor(
                            client,
                            api_key=settings.gemini_api_key,
                            model_name=settings.gemini_extraction_model,
                            timeout_seconds=settings.gemini_timeout_seconds,
                            max_attempts=settings.gemini_max_attempts,
                            retry_base_seconds=settings.gemini_retry_base_seconds,
                            usage_guard=safeguard_service,
                        ),
                        embedding_provider,
                        max_attempts=settings.processing_max_attempts,
                        stale_after_seconds=settings.processing_stale_after_seconds,
                        max_extraction_chunks=settings.max_extraction_chunks,
                        max_extraction_characters=settings.max_extraction_characters,
                    )
                    processor = DocumentPipelineService(
                        parsing_service,
                        enrichment_service,
                    )
                application.state.processing_service = BoundedDocumentProcessor(
                    processor,
                    max_concurrency=settings.processing_concurrency,
                )
            try:
                yield
            finally:
                await pool.close()
        return

    yield


docs_url, openapi_url = api_documentation_paths(settings.app_env)
app = FastAPI(
    title="Document Intelligence API",
    version="0.1.0",
    docs_url=docs_url,
    openapi_url=openapi_url,
    redoc_url=None,
    lifespan=lifespan,
)


app.add_exception_handler(SafeguardViolation, safeguard_violation_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=(LOCAL_CORS_ORIGIN_REGEX if settings.app_env == "development" else None),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(log_request)
app.include_router(api_router, prefix="/api/v1")
