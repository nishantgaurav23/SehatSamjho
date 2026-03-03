"""S4.3 — Welcome State tests.

18 tests covering _handle_welcome_state(): WELCOME_MESSAGE constant,
message sending, language selection, message ordering, session creation,
dispatch integration, error propagation, and PHI-safe logging.
"""

from __future__ import annotations

import os
from datetime import datetime
from io import StringIO
from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# Ensure test env vars are set BEFORE importing modules that read settings
# ---------------------------------------------------------------------------
_TEST_ENV = {
    "OPENAI_API_KEY": "sk-test-openai",
    "ANTHROPIC_API_KEY": "sk-ant-test-anthropic",
    "TWILIO_ACCOUNT_SID": "ACtest1234567890",
    "TWILIO_AUTH_TOKEN": "test-twilio-token",
    "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
    "BHASHINI_API_KEY": "test-bhashini-key",
    "BHASHINI_USER_ID": "test-bhashini-user",
    "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "S3_BUCKET": "test-bucket",
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
}
for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)

import pytest  # noqa: E402
from loguru import logger  # noqa: E402

from backend.app.api.webhooks import (  # noqa: E402
    WELCOME_MESSAGE,
    _dispatch,
    _handle_welcome_state,
)
from backend.app.models.schemas import (  # noqa: E402
    SessionState,
    SessionStatus,
    WebhookPayload,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PHONE = "whatsapp:+919876543210"
REQUEST_ID = "req-welcome-test-001"


def _make_payload(**overrides) -> WebhookPayload:
    defaults = {"from_number": PHONE, "body": "Hello", "num_media": 0}
    defaults.update(overrides)
    return WebhookPayload(**defaults)


def _mock_redis(get_value=None) -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=get_value)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


# ===========================================================================
# WELCOME_MESSAGE Constant (tests 1–3)
# ===========================================================================


def test_welcome_message_constant_exists():
    """WELCOME_MESSAGE is importable from backend.app.api.webhooks."""
    assert WELCOME_MESSAGE is not None


def test_welcome_message_is_nonempty_string():
    """WELCOME_MESSAGE is a non-empty string."""
    assert isinstance(WELCOME_MESSAGE, str)
    assert len(WELCOME_MESSAGE) > 0


def test_welcome_message_contains_service_name():
    """WELCOME_MESSAGE includes 'SehatSamjho'."""
    assert "SehatSamjho" in WELCOME_MESSAGE


def test_welcome_message_contains_privacy_note():
    """WELCOME_MESSAGE includes privacy/no-data-stored note."""
    lower = WELCOME_MESSAGE.lower()
    assert "no personal" in lower or "not store" in lower or "privacy" in lower


def test_welcome_message_contains_purpose():
    """WELCOME_MESSAGE mentions prescription translation."""
    lower = WELCOME_MESSAGE.lower()
    assert "prescription" in lower or "translat" in lower


# ===========================================================================
# Welcome Message Sending (tests 4–5)
# ===========================================================================


@pytest.mark.asyncio
async def test_welcome_sends_welcome_message():
    """_handle_welcome_state() calls send_text_message() with WELCOME_MESSAGE."""
    redis = _mock_redis()
    payload = _make_payload()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock) as mock_send,
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
    ):
        await _handle_welcome_state(payload, REQUEST_ID, redis)

        # Find the call that sent WELCOME_MESSAGE
        welcome_calls = [c for c in mock_send.call_args_list if c[0][1] == WELCOME_MESSAGE]
        assert len(welcome_calls) == 1
        assert welcome_calls[0][0][0] == PHONE


@pytest.mark.asyncio
async def test_welcome_sends_language_selection():
    """_handle_welcome_state() calls send_language_selection() with the user's phone number."""
    redis = _mock_redis()
    payload = _make_payload()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch(
            "backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock
        ) as mock_lang,
    ):
        await _handle_welcome_state(payload, REQUEST_ID, redis)

        mock_lang.assert_awaited_once_with(PHONE)


# ===========================================================================
# Message Ordering (test 6)
# ===========================================================================


@pytest.mark.asyncio
async def test_welcome_sends_messages_in_order():
    """Welcome text is sent before language selection."""
    redis = _mock_redis()
    payload = _make_payload()
    call_order = []

    async def mock_send_text(to, body):
        call_order.append("send_text")

    async def mock_send_lang(to):
        call_order.append("send_lang")

    with (
        patch("backend.app.api.webhooks.send_text_message", side_effect=mock_send_text),
        patch(
            "backend.app.api.webhooks.send_language_selection",
            side_effect=mock_send_lang,
        ),
    ):
        await _handle_welcome_state(payload, REQUEST_ID, redis)

    assert call_order == ["send_text", "send_lang"]


# ===========================================================================
# Session Creation (tests 7–10)
# ===========================================================================


@pytest.mark.asyncio
async def test_welcome_creates_session_waiting_for_language():
    """After sending messages, session with status=WAITING_FOR_LANGUAGE is saved."""
    redis = _mock_redis()
    payload = _make_payload()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
    ):
        await _handle_welcome_state(payload, REQUEST_ID, redis)

    # Verify _save_session was called via Redis.set
    redis.set.assert_awaited_once()
    stored_json = redis.set.call_args[0][1]
    session = SessionState.model_validate_json(stored_json)
    assert session.status == SessionStatus.WAITING_FOR_LANGUAGE


@pytest.mark.asyncio
async def test_welcome_session_has_request_id():
    """Saved session includes the request_id passed to the handler."""
    redis = _mock_redis()
    payload = _make_payload()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
    ):
        await _handle_welcome_state(payload, REQUEST_ID, redis)

    stored_json = redis.set.call_args[0][1]
    session = SessionState.model_validate_json(stored_json)
    assert session.request_id == REQUEST_ID


@pytest.mark.asyncio
async def test_welcome_session_has_created_at():
    """Saved session includes a valid created_at ISO timestamp."""
    redis = _mock_redis()
    payload = _make_payload()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
    ):
        await _handle_welcome_state(payload, REQUEST_ID, redis)

    stored_json = redis.set.call_args[0][1]
    session = SessionState.model_validate_json(stored_json)
    assert session.created_at is not None
    # Should be a valid ISO timestamp — parsing should not raise
    datetime.fromisoformat(session.created_at)


@pytest.mark.asyncio
async def test_welcome_session_no_language_set():
    """Saved session has language_code=None and language_name=None."""
    redis = _mock_redis()
    payload = _make_payload()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
    ):
        await _handle_welcome_state(payload, REQUEST_ID, redis)

    stored_json = redis.set.call_args[0][1]
    session = SessionState.model_validate_json(stored_json)
    assert session.language_code is None
    assert session.language_name is None


# ===========================================================================
# Dispatch Integration (tests 11–12)
# ===========================================================================


@pytest.mark.asyncio
async def test_dispatch_calls_welcome_for_new_user():
    """_dispatch() with no existing session calls _handle_welcome_state() (real, not mocked)."""
    redis = _mock_redis(get_value=None)
    payload = _make_payload()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
    ):
        # Call dispatch WITHOUT mocking _handle_welcome_state
        await _dispatch(payload, REQUEST_ID, redis)

    # Session should have been saved by the real welcome handler
    redis.set.assert_awaited_once()
    stored_json = redis.set.call_args[0][1]
    session = SessionState.model_validate_json(stored_json)
    assert session.status == SessionStatus.WAITING_FOR_LANGUAGE


@pytest.mark.asyncio
async def test_dispatch_welcome_creates_session():
    """Full flow: dispatch for new user -> welcome handler -> session exists."""
    redis = _mock_redis(get_value=None)
    payload = _make_payload()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock) as mock_send,
        patch(
            "backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock
        ) as mock_lang,
    ):
        await _dispatch(payload, REQUEST_ID, redis)

    # Both messages should have been sent
    assert mock_send.await_count >= 1
    mock_lang.assert_awaited_once()

    # Session should be stored
    redis.set.assert_awaited_once()
    stored_json = redis.set.call_args[0][1]
    session = SessionState.model_validate_json(stored_json)
    assert session.status == SessionStatus.WAITING_FOR_LANGUAGE
    assert session.request_id == REQUEST_ID


# ===========================================================================
# Error Propagation (tests 13–14)
# ===========================================================================


@pytest.mark.asyncio
async def test_welcome_propagates_send_error():
    """If send_text_message() raises, exception is not caught by the handler."""
    redis = _mock_redis()
    payload = _make_payload()

    with (
        patch(
            "backend.app.api.webhooks.send_text_message",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Twilio down"),
        ),
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
    ):
        with pytest.raises(RuntimeError, match="Twilio down"):
            await _handle_welcome_state(payload, REQUEST_ID, redis)


@pytest.mark.asyncio
async def test_welcome_propagates_language_selection_error():
    """If send_language_selection() raises, exception propagates."""
    redis = _mock_redis()
    payload = _make_payload()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch(
            "backend.app.api.webhooks.send_language_selection",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Language menu failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="Language menu failed"):
            await _handle_welcome_state(payload, REQUEST_ID, redis)


# ===========================================================================
# Logging (tests 15–16)
# ===========================================================================


@pytest.mark.asyncio
async def test_welcome_logs_with_request_id():
    """Handler logs include request_id in context."""
    redis = _mock_redis()
    payload = _make_payload()

    log_output = StringIO()
    handler_id = logger.add(
        log_output,
        format="{extra} {message}",
        level="DEBUG",
        filter=lambda r: "request_id" in r["extra"],
    )
    try:
        with (
            patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
            patch(
                "backend.app.api.webhooks.send_language_selection",
                new_callable=AsyncMock,
            ),
        ):
            await _handle_welcome_state(payload, REQUEST_ID, redis)

        log_text = log_output.getvalue()
        assert REQUEST_ID in log_text
    finally:
        logger.remove(handler_id)


@pytest.mark.asyncio
async def test_welcome_logs_no_raw_phone():
    """Log output does not contain raw phone numbers."""
    redis = _mock_redis()
    payload = _make_payload()

    log_output = StringIO()
    handler_id = logger.add(
        log_output,
        format="{extra} {message}",
        level="DEBUG",
    )
    try:
        with (
            patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
            patch(
                "backend.app.api.webhooks.send_language_selection",
                new_callable=AsyncMock,
            ),
        ):
            await _handle_welcome_state(payload, REQUEST_ID, redis)

        log_text = log_output.getvalue()
        # Raw phone number should NOT appear in logs
        assert "919876543210" not in log_text
        assert PHONE not in log_text
    finally:
        logger.remove(handler_id)


# ===========================================================================
# Function Signature (tests 17–18)
# ===========================================================================


def test_welcome_handler_signature_matches_stub():
    """_handle_welcome_state() accepts (payload, request_id, redis) — no return value."""
    import asyncio
    import inspect

    assert asyncio.iscoroutinefunction(_handle_welcome_state)
    sig = inspect.signature(_handle_welcome_state)
    params = list(sig.parameters.keys())
    assert params == ["payload", "request_id", "redis"]


def test_welcome_handler_returns_none():
    """_handle_welcome_state() return annotation is None."""
    import inspect

    sig = inspect.signature(_handle_welcome_state)
    # With `from __future__ import annotations`, annotation is the string 'None'
    assert sig.return_annotation in (None, "None", inspect.Parameter.empty)
