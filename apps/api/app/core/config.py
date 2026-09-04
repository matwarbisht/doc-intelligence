from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../../.env", ".env"),
        env_prefix="",
        extra="ignore",
        enable_decoding=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    database_url: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "documents"
    max_upload_bytes: int = 50 * 1024 * 1024
    unstructured_api_key: str | None = None
    unstructured_api_url: str | None = None
    unstructured_template_id: str = "hi_res_partition"
    unstructured_timeout_seconds: float = Field(default=300, gt=0)
    unstructured_poll_interval_seconds: float = Field(default=2, ge=0.1, le=30)
    processing_max_attempts: int = Field(default=3, ge=1, le=10)
    processing_stale_after_seconds: int = Field(default=15 * 60, ge=60)
    max_chunk_characters: int = Field(default=2_000, ge=100)
    gemini_api_key: str | None = None
    gemini_extraction_model: str = "gemini-3.6-flash"
    gemini_answer_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dimension: int = Field(default=768, ge=128, le=3072)
    gemini_timeout_seconds: float = Field(default=120, gt=0)
    gemini_embedding_concurrency: int = Field(default=5, ge=1, le=20)
    retrieval_candidate_limit: int = Field(default=10, ge=1, le=50)
    retrieval_max_sources: int = Field(default=8, ge=1, le=20)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
