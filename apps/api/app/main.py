from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
)
from app.services import (
    AuthenticationService,
    BoundedDocumentProcessor,
    CorpusQueryService,
    DocumentEnrichmentService,
    DocumentPipelineService,
    DocumentProcessingService,
    DocumentProcessor,
    DocumentService,
)

settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.log_format == "json")
LOCAL_CORS_ORIGIN_REGEX = r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
    application.state.authentication_service = None
    application.state.document_service = None
    application.state.processing_service = None
    application.state.query_service = None
    if settings.database_url and settings.supabase_url and settings.supabase_service_role_key:
        pool = await create_database_pool(settings.database_url)
        async with httpx.AsyncClient(timeout=30) as client:
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


app = FastAPI(
    title="Document Intelligence API",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)
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
