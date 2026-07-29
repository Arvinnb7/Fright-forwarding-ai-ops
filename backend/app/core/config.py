"""Application settings, loaded from environment / .env.

All secrets live in the environment; nothing is hardcoded. Settings are
imported as a singleton (`settings`) throughout the app.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ── Application ──────────────────────────────────────────
    app_env: str = "local"
    log_level: str = "INFO"
    secret_key: str = "change-me-to-a-long-random-string"
    # Encrypts mailbox credentials at rest. Falls back to a key derived from
    # SECRET_KEY when unset; set it explicitly to rotate independently.
    mailbox_encryption_key: str = ""
    access_token_expire_minutes: int = 43200  # 30 days
    algorithm: str = "HS256"

    admin_email: str = "operator@example.com"
    admin_password: str = "change-me"

    # ── Database ─────────────────────────────────────────────
    postgres_user: str = "freight"
    postgres_password: str = "freight"
    postgres_db: str = "freight_ai_ops"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    database_url: str | None = None

    # ── Redis / Celery ───────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # ── Email ingestion ──────────────────────────────────────
    email_poll_interval_minutes: int = 3
    email_fetch_batch_size: int = 25

    # ── File storage ─────────────────────────────────────────
    # Local disk by default; point it at a mounted volume in production so
    # uploads survive container replacement.
    storage_dir: str = "storage/files"
    max_upload_mb: int = 25

    # ── LLM ──────────────────────────────────────────────────
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-4-8"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # ── Company defaults (used in generated documents) ───────
    company_name: str = "Your Freight Company"
    user_full_name: str = "Operations Coordinator"
    email_signature: str = "Best regards,"
    default_markup_percent: float = 20.0
    default_currency: str = "USD"

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
