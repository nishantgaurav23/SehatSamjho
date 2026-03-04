"""Tests for S9.1 — Bhashini TTS API client (tts.py).

Covers: module import, BhashiniTTSError exception, constants, httpx lazy singleton,
payload builder, _call_bhashini() happy/error paths, logging with request_id, no PHI.
All 24 tests mock external dependencies (no real API calls).
"""

from __future__ import annotations

import base64
import inspect
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

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


# ===========================================================================
# Helpers
# ===========================================================================

SAMPLE_TEXT = "Take one tablet daily"
SAMPLE_LANG = "hi"
SAMPLE_REQUEST_ID = "req-tts-001"
SAMPLE_AUDIO_B64 = base64.b64encode(b"fake-audio-bytes-wav").decode()


def _make_bhashini_response(audio_b64: str = SAMPLE_AUDIO_B64) -> dict:
    """Build a mock Bhashini inference response with the given audio content."""
    return {
        "pipelineResponse": [{"output": [{"audio": [{"audioContent": audio_b64}]}]}],
    }


# ===========================================================================
# 1. Module importable
# ===========================================================================


def test_tts_module_importable():
    """Importing tts module succeeds without error."""
    import backend.app.services.tts  # noqa: F401


# ===========================================================================
# 2. BhashiniTTSError importable and is Exception subclass
# ===========================================================================


def test_bhashini_tts_error_importable():
    """BhashiniTTSError is importable and is an Exception subclass."""
    from backend.app.services.tts import BhashiniTTSError

    assert issubclass(BhashiniTTSError, Exception)


# ===========================================================================
# 3. BhashiniTTSError attributes
# ===========================================================================


def test_bhashini_tts_error_attributes():
    """BhashiniTTSError has message and status_code attributes."""
    from backend.app.services.tts import BhashiniTTSError

    err = BhashiniTTSError("test error", status_code=500)
    assert err.message == "test error"
    assert err.status_code == 500

    err_no_status = BhashiniTTSError("another error")
    assert err_no_status.message == "another error"
    assert err_no_status.status_code is None


# ===========================================================================
# 4. _call_bhashini importable and async
# ===========================================================================


def test_call_bhashini_importable():
    """_call_bhashini is importable and is an async function."""
    from backend.app.services.tts import _call_bhashini

    assert callable(_call_bhashini)
    assert inspect.iscoroutinefunction(_call_bhashini)


# ===========================================================================
# 5. BHASHINI_INFERENCE_URL defined
# ===========================================================================


def test_bhashini_inference_url_defined():
    """BHASHINI_INFERENCE_URL is a non-empty string starting with 'https'."""
    from backend.app.services.tts import BHASHINI_INFERENCE_URL

    assert isinstance(BHASHINI_INFERENCE_URL, str)
    assert len(BHASHINI_INFERENCE_URL) > 0
    assert BHASHINI_INFERENCE_URL.startswith("https")


# ===========================================================================
# 6. BHASHINI_TTS_GENDER defined
# ===========================================================================


def test_bhashini_tts_gender_defined():
    """BHASHINI_TTS_GENDER equals 'female'."""
    from backend.app.services.tts import BHASHINI_TTS_GENDER

    assert BHASHINI_TTS_GENDER == "female"


# ===========================================================================
# 7. _get_httpx_client returns AsyncClient
# ===========================================================================


def test_get_httpx_client_returns_async_client():
    """_get_httpx_client() returns an httpx.AsyncClient instance."""
    from backend.app.services.tts import _get_httpx_client, _reset_httpx_client

    _reset_httpx_client()
    client = _get_httpx_client()
    assert isinstance(client, httpx.AsyncClient)
    _reset_httpx_client()


# ===========================================================================
# 8. _get_httpx_client singleton
# ===========================================================================


def test_get_httpx_client_singleton():
    """Two calls to _get_httpx_client() return the same instance."""
    from backend.app.services.tts import _get_httpx_client, _reset_httpx_client

    _reset_httpx_client()
    c1 = _get_httpx_client()
    c2 = _get_httpx_client()
    assert c1 is c2
    _reset_httpx_client()


# ===========================================================================
# 9. _reset_httpx_client clears singleton
# ===========================================================================


def test_reset_httpx_client():
    """After reset, next call returns a new instance."""
    from backend.app.services.tts import _get_httpx_client, _reset_httpx_client

    _reset_httpx_client()
    c1 = _get_httpx_client()
    _reset_httpx_client()
    c2 = _get_httpx_client()
    assert c1 is not c2
    _reset_httpx_client()


# ===========================================================================
# 10. _build_bhashini_payload structure
# ===========================================================================


def test_build_payload_structure():
    """Payload has correct top-level keys: pipelineTasks, inputData."""
    from backend.app.services.tts import _build_bhashini_payload

    payload = _build_bhashini_payload(SAMPLE_TEXT, SAMPLE_LANG)
    assert "pipelineTasks" in payload
    assert "inputData" in payload
    assert isinstance(payload["pipelineTasks"], list)
    assert isinstance(payload["inputData"], dict)


# ===========================================================================
# 11. _build_bhashini_payload language code
# ===========================================================================


def test_build_payload_language_code():
    """Language code appears at pipelineTasks[0].config.language.sourceLanguage."""
    from backend.app.services.tts import _build_bhashini_payload

    payload = _build_bhashini_payload(SAMPLE_TEXT, "ta")
    source_lang = payload["pipelineTasks"][0]["config"]["language"]["sourceLanguage"]
    assert source_lang == "ta"


# ===========================================================================
# 12. _build_bhashini_payload text
# ===========================================================================


def test_build_payload_text():
    """Source text appears at inputData.input[0].source."""
    from backend.app.services.tts import _build_bhashini_payload

    payload = _build_bhashini_payload("hello world", SAMPLE_LANG)
    source_text = payload["inputData"]["input"][0]["source"]
    assert source_text == "hello world"


# ===========================================================================
# 13. _build_bhashini_payload gender
# ===========================================================================


def test_build_payload_gender():
    """Gender field is 'female'."""
    from backend.app.services.tts import _build_bhashini_payload

    payload = _build_bhashini_payload(SAMPLE_TEXT, SAMPLE_LANG)
    gender = payload["pipelineTasks"][0]["config"]["gender"]
    assert gender == "female"


# ===========================================================================
# 14. _build_bhashini_payload task type
# ===========================================================================


def test_build_payload_task_type():
    """taskType is 'tts'."""
    from backend.app.services.tts import _build_bhashini_payload

    payload = _build_bhashini_payload(SAMPLE_TEXT, SAMPLE_LANG)
    task_type = payload["pipelineTasks"][0]["taskType"]
    assert task_type == "tts"


# ===========================================================================
# 15. _call_bhashini happy path
# ===========================================================================


@pytest.mark.asyncio
async def test_call_bhashini_happy_path():
    """Mocked 200 response with base64 audio returns decoded bytes."""
    from backend.app.services.tts import _call_bhashini, _reset_httpx_client

    response_json = _make_bhashini_response()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("backend.app.services.tts._get_httpx_client", return_value=mock_client):
        _reset_httpx_client()
        result = await _call_bhashini(SAMPLE_TEXT, SAMPLE_LANG, SAMPLE_REQUEST_ID)

    assert isinstance(result, bytes)
    assert result == b"fake-audio-bytes-wav"


# ===========================================================================
# 16. _call_bhashini sends correct headers
# ===========================================================================


@pytest.mark.asyncio
async def test_call_bhashini_sends_correct_headers():
    """Authorization and Content-Type headers are present in the POST."""
    from backend.app.services.tts import _call_bhashini, _reset_httpx_client

    response_json = _make_bhashini_response()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    mock_settings = MagicMock()
    mock_settings.BHASHINI_API_KEY = "bhashini-key-123"
    mock_settings.BHASHINI_USER_ID = "bhashini-user-456"

    with (
        patch("backend.app.services.tts._get_httpx_client", return_value=mock_client),
        patch("backend.app.core.config.settings", mock_settings),
    ):
        _reset_httpx_client()
        await _call_bhashini(SAMPLE_TEXT, SAMPLE_LANG, SAMPLE_REQUEST_ID)

    call_kwargs = mock_client.post.call_args
    headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
    assert headers.get("Authorization") == "bhashini-key-123"
    assert headers.get("Content-Type") == "application/json"
    assert headers.get("userID") == "bhashini-user-456"


# ===========================================================================
# 17. _call_bhashini sends correct payload
# ===========================================================================


@pytest.mark.asyncio
async def test_call_bhashini_sends_correct_payload():
    """POSTed JSON matches expected Bhashini payload structure."""
    from backend.app.services.tts import _call_bhashini, _reset_httpx_client

    response_json = _make_bhashini_response()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("backend.app.services.tts._get_httpx_client", return_value=mock_client):
        _reset_httpx_client()
        await _call_bhashini(SAMPLE_TEXT, SAMPLE_LANG, SAMPLE_REQUEST_ID)

    call_kwargs = mock_client.post.call_args
    posted_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert posted_json["pipelineTasks"][0]["taskType"] == "tts"
    assert posted_json["pipelineTasks"][0]["config"]["language"]["sourceLanguage"] == SAMPLE_LANG
    assert posted_json["inputData"]["input"][0]["source"] == SAMPLE_TEXT


# ===========================================================================
# 18. _call_bhashini HTTP error raises BhashiniTTSError
# ===========================================================================


@pytest.mark.asyncio
async def test_call_bhashini_http_error_raises():
    """500 response raises BhashiniTTSError."""
    from backend.app.services.tts import BhashiniTTSError, _call_bhashini, _reset_httpx_client

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=mock_response
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("backend.app.services.tts._get_httpx_client", return_value=mock_client):
        _reset_httpx_client()
        with pytest.raises(BhashiniTTSError) as exc_info:
            await _call_bhashini(SAMPLE_TEXT, SAMPLE_LANG, SAMPLE_REQUEST_ID)
        assert exc_info.value.status_code == 500


# ===========================================================================
# 19. _call_bhashini empty audio raises BhashiniTTSError
# ===========================================================================


@pytest.mark.asyncio
async def test_call_bhashini_empty_audio_raises():
    """Response with empty audioContent raises BhashiniTTSError."""
    from backend.app.services.tts import BhashiniTTSError, _call_bhashini, _reset_httpx_client

    response_json = _make_bhashini_response(audio_b64="")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("backend.app.services.tts._get_httpx_client", return_value=mock_client):
        _reset_httpx_client()
        with pytest.raises(BhashiniTTSError):
            await _call_bhashini(SAMPLE_TEXT, SAMPLE_LANG, SAMPLE_REQUEST_ID)


# ===========================================================================
# 20. _call_bhashini malformed JSON raises BhashiniTTSError
# ===========================================================================


@pytest.mark.asyncio
async def test_call_bhashini_malformed_json_raises():
    """Non-JSON response raises BhashiniTTSError."""
    from backend.app.services.tts import BhashiniTTSError, _call_bhashini, _reset_httpx_client

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("No JSON")
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("backend.app.services.tts._get_httpx_client", return_value=mock_client):
        _reset_httpx_client()
        with pytest.raises(BhashiniTTSError):
            await _call_bhashini(SAMPLE_TEXT, SAMPLE_LANG, SAMPLE_REQUEST_ID)


# ===========================================================================
# 21. _call_bhashini timeout raises BhashiniTTSError
# ===========================================================================


@pytest.mark.asyncio
async def test_call_bhashini_timeout_raises():
    """httpx.TimeoutException raises BhashiniTTSError."""
    from backend.app.services.tts import BhashiniTTSError, _call_bhashini, _reset_httpx_client

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Connection timed out"))

    with patch("backend.app.services.tts._get_httpx_client", return_value=mock_client):
        _reset_httpx_client()
        with pytest.raises(BhashiniTTSError):
            await _call_bhashini(SAMPLE_TEXT, SAMPLE_LANG, SAMPLE_REQUEST_ID)


# ===========================================================================
# 22. _call_bhashini missing audio key raises BhashiniTTSError
# ===========================================================================


@pytest.mark.asyncio
async def test_call_bhashini_missing_audio_key_raises():
    """Response JSON missing expected keys raises BhashiniTTSError."""
    from backend.app.services.tts import BhashiniTTSError, _call_bhashini, _reset_httpx_client

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"pipelineResponse": [{"output": [{}]}]}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("backend.app.services.tts._get_httpx_client", return_value=mock_client):
        _reset_httpx_client()
        with pytest.raises(BhashiniTTSError):
            await _call_bhashini(SAMPLE_TEXT, SAMPLE_LANG, SAMPLE_REQUEST_ID)


# ===========================================================================
# 23. _call_bhashini logs request_id
# ===========================================================================


@pytest.mark.asyncio
async def test_call_bhashini_logs_request_id():
    """Loguru log output contains the request_id."""
    from backend.app.services.tts import _call_bhashini, _reset_httpx_client

    response_json = _make_bhashini_response()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()
    # Provide a len()-able content for response size logging
    mock_response.content = b"x" * 100

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    log_messages: list[str] = []

    def _sink(message):
        log_messages.append(str(message))

    from loguru import logger

    handler_id = logger.add(_sink, level="DEBUG")
    try:
        with patch("backend.app.services.tts._get_httpx_client", return_value=mock_client):
            _reset_httpx_client()
            await _call_bhashini(SAMPLE_TEXT, SAMPLE_LANG, SAMPLE_REQUEST_ID)
    finally:
        logger.remove(handler_id)

    combined = " ".join(log_messages)
    assert SAMPLE_REQUEST_ID in combined


# ===========================================================================
# 24. _call_bhashini no PHI in logs
# ===========================================================================


@pytest.mark.asyncio
async def test_call_bhashini_no_phi_in_logs():
    """Logs do not contain the input text or audio content."""
    from backend.app.services.tts import _call_bhashini, _reset_httpx_client

    sensitive_text = "Patient should take Metformin 500mg twice daily"
    response_json = _make_bhashini_response()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_json
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b"x" * 100

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    log_messages: list[str] = []

    def _sink(message):
        log_messages.append(str(message))

    from loguru import logger

    handler_id = logger.add(_sink, level="DEBUG")
    try:
        with patch("backend.app.services.tts._get_httpx_client", return_value=mock_client):
            _reset_httpx_client()
            await _call_bhashini(sensitive_text, SAMPLE_LANG, "req-phi-test")
    finally:
        logger.remove(handler_id)

    combined = " ".join(log_messages)
    # Input text must NOT appear in logs
    assert sensitive_text not in combined
    # Base64 audio content must NOT appear in logs
    assert SAMPLE_AUDIO_B64 not in combined
