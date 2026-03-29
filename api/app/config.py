"""
ScholarGuard API configuration.

Loads settings from environment variables and .env file using pydantic-settings.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/scholarguard"

    # ── Redis ───────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── MinIO / S3 ──────────────────────────────────────────────────────
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "scholarguard"

    # ── JWT ──────────────────────────────────────────────────────────────
    jwt_secret: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # ── Ollama / vLLM ──────────────────────────────────────────────────
    ollama_url: str = "http://localhost:11434"
    vllm_url: Optional[str] = "http://192.168.31.18:8001/v1"

    # ── Optional LLM provider keys ──────────────────────────────────────
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # ── Formula / parameter versioning ──────────────────────────────────
    formula_version: str = "1.0.0"
    param_version: str = "1.0.0"

    # ── General ─────────────────────────────────────────────────────────
    log_level: str = "INFO"
    environment: str = "development"
    api_key_header: str = "X-API-Key"
    allowed_api_keys: list[str] = []


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
