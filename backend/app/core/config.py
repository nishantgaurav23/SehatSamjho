"""Centralised application settings loaded from environment variables via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration. Secrets have no defaults (fail fast on missing)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── OpenAI (GPT-4O Vision) ──────────────────────────────────────────────
    OPENAI_API_KEY: str

    # ── Anthropic (Claude Sonnet 4.6) ───────────────────────────────────────
    ANTHROPIC_API_KEY: str

    # ── Twilio (WhatsApp) ───────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_FROM: str

    # ── Bhashini (TTS) ──────────────────────────────────────────────────────
    BHASHINI_API_KEY: str
    BHASHINI_USER_ID: str

    # ── AWS (S3 audio storage) ──────────────────────────────────────────────
    # Optional — EC2 uses IAM role; only needed for local dev with explicit keys
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET: str = "sehatsamjho-audio"

    # ── Database (PostgreSQL async) ─────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sehatsamjho"

    # ── Redis (sessions + cache) ────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"


settings = Settings()
