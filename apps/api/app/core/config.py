from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_prefix="",
        extra="ignore",
        enable_decoding=False,
    )

    app_env: str = "development"
    log_level: str = Field(
        default="INFO", validation_alias=AliasChoices("LOG_LEVEL", "APP_LOG_LEVEL")
    )
    log_format: Literal["console", "json"] = "console"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        validation_alias=AliasChoices("CORS_ORIGINS", "APP_CORS_ORIGINS"),
    )
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "documents"
    max_upload_bytes: int = 50 * 1024 * 1024
    unstructured_api_key: str | None = None
    unstructured_api_url: str | None = None
    unstructured_template_id: str = "hi_res_partition"
    unstructured_timeout_seconds: float = Field(default=300, gt=0)
    unstructured_poll_interval_seconds: float = Field(default=2, ge=0.1, le=30)
    unstructured_concurrency: int = Field(default=1, ge=1, le=10)
    unstructured_max_attempts: int = Field(default=3, ge=1, le=10)
    unstructured_retry_base_seconds: float = Field(default=1, ge=0, le=30)
    processing_max_attempts: int = Field(default=3, ge=1, le=10)
    processing_concurrency: int = Field(default=3, ge=1, le=20)
    processing_stale_after_seconds: int = Field(default=15 * 60, ge=60)
    max_chunk_characters: int = Field(default=2_000, ge=100)
    max_extraction_chunks: int = Field(default=250, ge=1, le=2_000)
    max_extraction_characters: int = Field(default=200_000, ge=1_000, le=2_000_000)
    gemini_api_key: str | None = None
    gemini_extraction_model: str = "gemini-3.6-flash"
    gemini_answer_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimension: int = Field(default=768, ge=128, le=3072)
    gemini_timeout_seconds: float = Field(default=120, gt=0)
    gemini_embedding_concurrency: int = Field(default=5, ge=1, le=20)
    gemini_max_attempts: int = Field(default=3, ge=1, le=5)
    gemini_retry_base_seconds: float = Field(default=0.5, ge=0, le=10)
    retrieval_candidate_limit: int = Field(default=10, ge=1, le=50)
    retrieval_max_sources: int = Field(default=8, ge=1, le=20)
    public_signup_enabled: bool = True
    uploads_enabled: bool = True
    processing_enabled: bool = True
    processing_retries_enabled: bool = True
    ask_enabled: bool = True
    user_uploads_per_hour: int = Field(default=10, ge=1)
    user_documents_per_day: int = Field(default=25, ge=1)
    user_upload_bytes_per_day: int = Field(default=262_144_000, ge=1)
    user_asks_per_hour: int = Field(default=30, ge=1)
    user_asks_per_day: int = Field(default=100, ge=1)
    user_retries_per_hour: int = Field(default=5, ge=1)
    user_retries_per_day: int = Field(default=10, ge=1)
    user_max_documents: int = Field(default=100, ge=1)
    retry_cooldown_seconds: int = Field(default=300, ge=1)
    ip_uploads_per_hour: int = Field(default=30, ge=1)
    ip_asks_per_hour: int = Field(default=120, ge=1)
    ip_hash_salt: str = Field(default="local-development-only", min_length=16)
    global_documents_per_day: int = Field(default=250, ge=1)
    global_upload_bytes_per_day: int = Field(default=2_621_440_000, ge=1)
    global_asks_per_day: int = Field(default=500, ge=1)
    user_unstructured_attempts_per_day: int = Field(default=30, ge=1)
    global_unstructured_attempts_per_day: int = Field(default=250, ge=1)
    user_gemini_extractions_per_day: int = Field(default=30, ge=1)
    global_gemini_extractions_per_day: int = Field(default=250, ge=1)
    user_gemini_embedding_calls_per_day: int = Field(default=1_000, ge=1)
    global_gemini_embedding_calls_per_day: int = Field(default=10_000, ge=1)
    user_gemini_query_embeddings_per_day: int = Field(default=100, ge=1)
    global_gemini_query_embeddings_per_day: int = Field(default=500, ge=1)
    user_gemini_answers_per_day: int = Field(default=100, ge=1)
    global_gemini_answers_per_day: int = Field(default=500, ge=1)
    provider_circuit_failure_threshold: int = Field(default=5, ge=1)
    provider_circuit_window_seconds: int = Field(default=60, ge=1)
    provider_circuit_cooldown_seconds: int = Field(default=60, ge=1)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def require_production_ip_hash_salt(self) -> "Settings":
        if self.app_env == "production" and len(self.ip_hash_salt) < 32:
            raise ValueError("IP_HASH_SALT must contain at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
