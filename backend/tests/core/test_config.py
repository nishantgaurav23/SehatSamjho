"""Tests for backend.app.core.config — S1.3 pydantic-settings config."""

import pytest
from pydantic import ValidationError


# ── Required env vars (9 secrets with no defaults) ──────────────────────────
REQUIRED_ENV_VARS = {
    "OPENAI_API_KEY": "sk-test-openai",
    "ANTHROPIC_API_KEY": "sk-ant-test-anthropic",
    "TWILIO_ACCOUNT_SID": "ACtest1234567890",
    "TWILIO_AUTH_TOKEN": "test-twilio-token",
    "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
    "BHASHINI_API_KEY": "test-bhashini-key",
    "BHASHINI_USER_ID": "test-bhashini-user",
    "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
}

# ── All 12 fields (required + defaulted) ────────────────────────────────────
ALL_FIELDS = {
    **REQUIRED_ENV_VARS,
    "S3_BUCKET": "sehatsamjho-audio",
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/sehatsamjho",
    "REDIS_URL": "redis://localhost:6379/0",
}


@pytest.fixture()
def _env_with_all_vars(monkeypatch):
    """Set all 12 env vars so Settings() can be instantiated."""
    for key, value in ALL_FIELDS.items():
        monkeypatch.setenv(key, value)


@pytest.fixture()
def _env_with_required_only(monkeypatch):
    """Set only the 9 required env vars (no defaults)."""
    for key, value in REQUIRED_ENV_VARS.items():
        monkeypatch.setenv(key, value)
    # Explicitly unset defaulted vars so they fall back to defaults
    for key in ("S3_BUCKET", "DATABASE_URL", "REDIS_URL"):
        monkeypatch.delenv(key, raising=False)


# ── Test 1: Settings class exists ───────────────────────────────────────────
def test_settings_class_exists():
    """Settings class is importable from backend.app.core.config."""
    from backend.app.core.config import Settings

    assert Settings is not None


# ── Test 2: Settings inherits BaseSettings ──────────────────────────────────
def test_settings_inherits_base_settings():
    """Settings must be a subclass of pydantic_settings.BaseSettings."""
    from pydantic_settings import BaseSettings

    from backend.app.core.config import Settings

    assert issubclass(Settings, BaseSettings)


# ── Test 3: Settings has all 12 fields ──────────────────────────────────────
def test_settings_has_all_fields():
    """Settings class declares all 12 expected fields."""
    from backend.app.core.config import Settings

    field_names = set(Settings.model_fields.keys())
    expected = set(ALL_FIELDS.keys())
    assert expected.issubset(field_names), f"Missing fields: {expected - field_names}"


# ── Test 4: Settings loads from env vars ────────────────────────────────────
@pytest.mark.usefixtures("_env_with_all_vars")
def test_settings_loads_from_env():
    """Settings() succeeds when all env vars are set and values match."""
    from backend.app.core.config import Settings

    s = Settings()
    assert s.OPENAI_API_KEY == "sk-test-openai"
    assert s.ANTHROPIC_API_KEY == "sk-ant-test-anthropic"
    assert s.TWILIO_ACCOUNT_SID == "ACtest1234567890"
    assert s.TWILIO_AUTH_TOKEN == "test-twilio-token"
    assert s.TWILIO_WHATSAPP_FROM == "whatsapp:+14155238886"
    assert s.BHASHINI_API_KEY == "test-bhashini-key"
    assert s.BHASHINI_USER_ID == "test-bhashini-user"
    assert s.AWS_ACCESS_KEY_ID == "AKIAIOSFODNN7EXAMPLE"
    assert s.AWS_SECRET_ACCESS_KEY == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    assert s.S3_BUCKET == "sehatsamjho-audio"


# ── Test 5: Missing required field raises ValidationError ───────────────────
def test_settings_required_fields_missing(monkeypatch):
    """Omitting a required field (OPENAI_API_KEY) raises ValidationError."""
    from backend.app.core.config import Settings

    # Set all required vars except OPENAI_API_KEY
    for key, value in REQUIRED_ENV_VARS.items():
        if key != "OPENAI_API_KEY":
            monkeypatch.setenv(key, value)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings()


# ── Test 6: S3_BUCKET default ──────────────────────────────────────────────
@pytest.mark.usefixtures("_env_with_required_only")
def test_settings_s3_bucket_default():
    """S3_BUCKET defaults to 'sehatsamjho-audio' when not set."""
    from backend.app.core.config import Settings

    s = Settings()
    assert s.S3_BUCKET == "sehatsamjho-audio"


# ── Test 7: DATABASE_URL default ───────────────────────────────────────────
@pytest.mark.usefixtures("_env_with_required_only")
def test_settings_database_url_default():
    """DATABASE_URL defaults to local asyncpg connection string when not set."""
    from backend.app.core.config import Settings

    s = Settings()
    assert s.DATABASE_URL == "postgresql+asyncpg://postgres:postgres@localhost:5432/sehatsamjho"


# ── Test 8: REDIS_URL default ──────────────────────────────────────────────
@pytest.mark.usefixtures("_env_with_required_only")
def test_settings_redis_url_default():
    """REDIS_URL defaults to 'redis://localhost:6379/0' when not set."""
    from backend.app.core.config import Settings

    s = Settings()
    assert s.REDIS_URL == "redis://localhost:6379/0"


# ── Test 9: Module-level singleton exported ─────────────────────────────────
@pytest.mark.usefixtures("_env_with_all_vars")
def test_settings_singleton_exported():
    """A module-level `settings` attribute exists on backend.app.core.config."""
    import backend.app.core.config as config_module

    assert hasattr(config_module, "settings"), "Missing module-level `settings` singleton"


# ── Test 10: model_config includes env_file ─────────────────────────────────
def test_settings_env_file_configured():
    """Settings.model_config includes env_file='.env'."""
    from backend.app.core.config import Settings

    cfg = Settings.model_config
    assert cfg.get("env_file") == ".env", f"env_file should be '.env', got {cfg.get('env_file')}"
