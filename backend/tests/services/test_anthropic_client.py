"""Tests for S7.1 — Anthropic async client + prompt templates (translation.py).

Covers: module import, lazy singleton, API key wiring, reset, lazy settings import,
module docstring, expected names, constants (CLAUDE_MODEL, TRANSLATION_MAX_TOKENS,
TRANSLATION_TEMPERATURE). All 13 tests mock external dependencies (no real API calls).
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Ensure test env vars are set BEFORE importing modules that read settings
# ---------------------------------------------------------------------------
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest1234567890")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
os.environ.setdefault("BHASHINI_API_KEY", "test-bhashini-key")
os.environ.setdefault("BHASHINI_USER_ID", "test-bhashini-user")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-aws-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import anthropic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_import():
    """Force a clean re-import of translation module to test import-time behaviour."""
    import importlib

    import backend.app.services.translation as mod

    importlib.reload(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. Module importable
# ---------------------------------------------------------------------------


def test_translation_module_importable():
    """Importing translation module succeeds without error."""
    import backend.app.services.translation  # noqa: F401


# ---------------------------------------------------------------------------
# 2. _get_client returns AsyncAnthropic
# ---------------------------------------------------------------------------


def test_get_client_returns_async_anthropic():
    """_get_client() returns an anthropic.AsyncAnthropic instance."""
    from backend.app.services.translation import _get_client, _reset_client

    _reset_client()
    client = _get_client()
    assert isinstance(client, anthropic.AsyncAnthropic)
    _reset_client()


# ---------------------------------------------------------------------------
# 3. Singleton behaviour
# ---------------------------------------------------------------------------


def test_get_client_singleton():
    """Two calls to _get_client() return the exact same object."""
    from backend.app.services.translation import _get_client, _reset_client

    _reset_client()
    c1 = _get_client()
    c2 = _get_client()
    assert c1 is c2
    _reset_client()


# ---------------------------------------------------------------------------
# 4. API key wiring
# ---------------------------------------------------------------------------


def test_get_client_uses_api_key():
    """The returned client uses the API key from settings."""
    from backend.app.services.translation import _get_client, _reset_client

    mock_settings = MagicMock()
    mock_settings.ANTHROPIC_API_KEY = "sk-ant-test-unique-key"
    with patch("backend.app.core.config.settings", mock_settings):
        _reset_client()
        client = _get_client()
        assert client.api_key == "sk-ant-test-unique-key"
        _reset_client()


# ---------------------------------------------------------------------------
# 5. _reset_client clears cache
# ---------------------------------------------------------------------------


def test_reset_client_clears_cache():
    """After _reset_client(), _get_client() creates a new instance."""
    from backend.app.services.translation import _get_client, _reset_client

    _reset_client()
    c1 = _get_client()
    _reset_client()
    c2 = _get_client()
    assert c1 is not c2
    _reset_client()


# ---------------------------------------------------------------------------
# 6. Lazy settings import — importing module does NOT trigger Settings()
# ---------------------------------------------------------------------------


def test_get_client_lazy_settings_import():
    """Importing translation does not import settings at module level."""
    import inspect

    mod = _fresh_import()
    source = inspect.getsource(mod)

    # No module-level import of settings (should be inside _get_client only)
    lines = source.split("\n")
    for line in lines:
        stripped = line.strip()
        # Skip lines inside function bodies (indented)
        if line and not line[0].isspace() and "import" in stripped:
            assert "config" not in stripped, f"Module-level import of config found: {stripped}"


# ---------------------------------------------------------------------------
# 7. Client created with correct constructor args
# ---------------------------------------------------------------------------


def test_get_client_creates_client_with_correct_args():
    """anthropic.AsyncAnthropic is called with api_key matching settings."""
    from backend.app.services.translation import _get_client, _reset_client

    mock_settings = MagicMock()
    mock_settings.ANTHROPIC_API_KEY = "sk-ant-constructor-test"
    with (
        patch("backend.app.core.config.settings", mock_settings),
        patch("backend.app.services.translation.anthropic.AsyncAnthropic") as mock_cls,
    ):
        mock_cls.return_value = MagicMock()
        _reset_client()
        _get_client()
        mock_cls.assert_called_once_with(api_key="sk-ant-constructor-test")
        _reset_client()


# ---------------------------------------------------------------------------
# 8. Module has docstring
# ---------------------------------------------------------------------------


def test_module_has_docstring():
    """translation.__doc__ is non-empty."""
    import backend.app.services.translation as mod

    assert mod.__doc__ is not None
    assert len(mod.__doc__.strip()) > 0


# ---------------------------------------------------------------------------
# 9. Module exposes expected names
# ---------------------------------------------------------------------------


def test_module_exposes_expected_names():
    """Module has all expected names in its namespace."""
    import backend.app.services.translation as mod

    expected = [
        "_get_client",
        "_reset_client",
        "CLAUDE_MODEL",
        "TRANSLATION_MAX_TOKENS",
        "TRANSLATION_TEMPERATURE",
    ]
    for name in expected:
        assert hasattr(mod, name), f"Missing expected name: {name}"

    assert callable(mod._get_client)
    assert callable(mod._reset_client)


# ---------------------------------------------------------------------------
# 10. After reset, fresh settings are read
# ---------------------------------------------------------------------------


def test_get_client_after_reset_uses_fresh_settings():
    """After reset, _get_client() reads settings again (new key is picked up)."""
    from backend.app.services.translation import _get_client, _reset_client

    mock_settings = MagicMock()
    with patch("backend.app.core.config.settings", mock_settings):
        mock_settings.ANTHROPIC_API_KEY = "key-v1"
        _reset_client()
        c1 = _get_client()
        assert c1.api_key == "key-v1"

        mock_settings.ANTHROPIC_API_KEY = "key-v2"
        _reset_client()
        c2 = _get_client()
        assert c2.api_key == "key-v2"
        assert c1 is not c2
        _reset_client()


# ---------------------------------------------------------------------------
# 11. CLAUDE_MODEL constant
# ---------------------------------------------------------------------------


def test_claude_model_constant():
    """CLAUDE_MODEL equals 'claude-sonnet-4-6'."""
    from backend.app.services.translation import CLAUDE_MODEL

    assert CLAUDE_MODEL == "claude-sonnet-4-6"
    assert isinstance(CLAUDE_MODEL, str)


# ---------------------------------------------------------------------------
# 12. TRANSLATION_MAX_TOKENS constant
# ---------------------------------------------------------------------------


def test_translation_max_tokens_constant():
    """TRANSLATION_MAX_TOKENS equals 1024."""
    from backend.app.services.translation import TRANSLATION_MAX_TOKENS

    assert TRANSLATION_MAX_TOKENS == 1024
    assert isinstance(TRANSLATION_MAX_TOKENS, int)


# ---------------------------------------------------------------------------
# 13. TRANSLATION_TEMPERATURE constant
# ---------------------------------------------------------------------------


def test_translation_temperature_constant():
    """TRANSLATION_TEMPERATURE equals 0.3."""
    from backend.app.services.translation import TRANSLATION_TEMPERATURE

    assert TRANSLATION_TEMPERATURE == 0.3
    assert isinstance(TRANSLATION_TEMPERATURE, float)
