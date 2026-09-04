from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.db import create_database_pool
from app.providers import SupabaseObjectStorage, UnstructuredDocumentParser
from app.repositories import PostgresDocumentRepository, PostgresProcessingRepository
from app.services import DocumentProcessingService, DocumentService

settings = get_settings()
LOCAL_CORS_ORIGIN_REGEX = r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None]:
    application.state.document_service = None
    application.state.processing_service = None
    if settings.database_url and settings.supabase_url and settings.supabase_service_role_key:
        pool = await create_database_pool(settings.database_url)
        async with httpx.AsyncClient(timeout=30) as client:
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
            if settings.unstructured_api_url and settings.unstructured_api_key:
                parser = UnstructuredDocumentParser(
                    client,
                    api_url=settings.unstructured_api_url,
                    api_key=settings.unstructured_api_key,
                    template_id=settings.unstructured_template_id,
                    timeout_seconds=settings.unstructured_timeout_seconds,
                    poll_interval_seconds=settings.unstructured_poll_interval_seconds,
                )
                application.state.processing_service = DocumentProcessingService(
                    PostgresProcessingRepository(pool),
                    storage,
                    parser,
                    max_attempts=settings.processing_max_attempts,
                    stale_after_seconds=settings.processing_stale_after_seconds,
                    max_chunk_characters=settings.max_chunk_characters,
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
app.include_router(api_router, prefix="/api/v1")
