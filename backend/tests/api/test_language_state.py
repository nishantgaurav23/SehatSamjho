"""S4.4 — Language State tests.

20 tests covering _handle_language_state(): IMAGE_PROMPT_MESSAGE and
LANGUAGE_NOT_RECOGNISED_MESSAGE constants, valid language selection,
"More languages" path, invalid input path, error propagation, and
PHI-safe logging.
"""

from __future__ import annotations

import os
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
    IMAGE_PROMPT_MESSAGE,
    LANGUAGE_NOT_RECOGNISED_MESSAGE,
    _handle_language_state,
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
REQUEST_ID = "req-lang-test-001"
CREATED_AT = "2026-03-01T10:00:00+00:00"


def _make_payload(**overrides) -> WebhookPayload:
    defaults = {"from_number": PHONE, "body": "1", "num_media": 0}
    defaults.update(overrides)
    return WebhookPayload(**defaults)


def _make_session(**overrides) -> SessionState:
    defaults = {
        "status": SessionStatus.WAITING_FOR_LANGUAGE,
        "language_code": None,
        "language_name": None,
        "request_id": REQUEST_ID,
        "created_at": CREATED_AT,
    }
    defaults.update(overrides)
    return SessionState(**defaults)


def _mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


# ===========================================================================
# Constants (tests 1–3)
# ===========================================================================


def test_image_prompt_message_exists():
    """IMAGE_PROMPT_MESSAGE is importable from backend.app.api.webhooks."""
    assert IMAGE_PROMPT_MESSAGE is not None
    assert isinstance(IMAGE_PROMPT_MESSAGE, str)
    assert len(IMAGE_PROMPT_MESSAGE) > 0


def test_image_prompt_message_mentions_prescription():
    """IMAGE_PROMPT_MESSAGE mentions prescription/photo."""
    lower = IMAGE_PROMPT_MESSAGE.lower()
    assert "prescription" in lower or "photo" in lower or "image" in lower


def test_language_not_recognised_message_exists():
    """LANGUAGE_NOT_RECOGNISED_MESSAGE is importable and non-empty."""
    assert LANGUAGE_NOT_RECOGNISED_MESSAGE is not None
    assert isinstance(LANGUAGE_NOT_RECOGNISED_MESSAGE, str)
    assert len(LANGUAGE_NOT_RECOGNISED_MESSAGE) > 0


# ===========================================================================
# Valid language selection (tests 4–10)
# ===========================================================================


@pytest.mark.asyncio
async def test_language_calls_parse_language_selection():
    """Handler calls parse_language_selection(payload.body)."""
    redis = _mock_redis()
    payload = _make_payload(body="1")
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=("Hindi", "hi"),
        ) as mock_parse,
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        mock_parse.assert_called_once_with("1")


@pytest.mark.asyncio
async def test_valid_language_updates_session_status():
    """Valid language -> session saved with status=WAITING_FOR_IMAGE."""
    redis = _mock_redis()
    payload = _make_payload(body="1")
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=("Hindi", "hi"),
        ),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        mock_save.assert_awaited_once()
        saved_session = mock_save.call_args[0][1]
        assert saved_session.status == SessionStatus.WAITING_FOR_IMAGE


@pytest.mark.asyncio
async def test_valid_language_stores_language_code():
    """Valid language -> session has correct language_code."""
    redis = _mock_redis()
    payload = _make_payload(body="2")
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=("Bengali", "bn"),
        ),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        saved_session = mock_save.call_args[0][1]
        assert saved_session.language_code == "bn"


@pytest.mark.asyncio
async def test_valid_language_stores_language_name():
    """Valid language -> session has correct language_name."""
    redis = _mock_redis()
    payload = _make_payload(body="2")
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=("Bengali", "bn"),
        ),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        saved_session = mock_save.call_args[0][1]
        assert saved_session.language_name == "Bengali"


@pytest.mark.asyncio
async def test_valid_language_preserves_request_id():
    """Updated session retains original request_id."""
    redis = _mock_redis()
    payload = _make_payload(body="1")
    session = _make_session(request_id="original-req-id-999")

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=("Hindi", "hi"),
        ),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
    ):
        await _handle_language_state(payload, session, "original-req-id-999", redis)

        saved_session = mock_save.call_args[0][1]
        assert saved_session.request_id == "original-req-id-999"


@pytest.mark.asyncio
async def test_valid_language_preserves_created_at():
    """Updated session retains original created_at."""
    redis = _mock_redis()
    payload = _make_payload(body="1")
    original_ts = "2026-01-15T08:30:00+00:00"
    session = _make_session(created_at=original_ts)

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=("Hindi", "hi"),
        ),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        saved_session = mock_save.call_args[0][1]
        assert saved_session.created_at == original_ts


@pytest.mark.asyncio
async def test_valid_language_sends_image_prompt():
    """Valid language -> send_text_message() called with IMAGE_PROMPT_MESSAGE."""
    redis = _mock_redis()
    payload = _make_payload(body="1")
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=("Hindi", "hi"),
        ),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock) as mock_send,
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        mock_send.assert_awaited_once_with(PHONE, IMAGE_PROMPT_MESSAGE)


# ===========================================================================
# More languages (tests 11–13)
# ===========================================================================


@pytest.mark.asyncio
async def test_more_languages_sends_extended_list():
    """Input '9' -> send_more_languages() called."""
    redis = _mock_redis()
    payload = _make_payload(body="9")
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_more_languages", new_callable=AsyncMock) as mock_more,
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        mock_more.assert_awaited_once_with(PHONE)


@pytest.mark.asyncio
async def test_more_languages_resends_selection():
    """Input '9' -> send_language_selection() called after extended list."""
    redis = _mock_redis()
    payload = _make_payload(body="9")
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_more_languages", new_callable=AsyncMock),
        patch(
            "backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock
        ) as mock_sel,
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        mock_sel.assert_awaited_once_with(PHONE)


@pytest.mark.asyncio
async def test_more_languages_does_not_change_session():
    """Input '9' -> _save_session() NOT called (session unchanged)."""
    redis = _mock_redis()
    payload = _make_payload(body="9")
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_more_languages", new_callable=AsyncMock),
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        mock_save.assert_not_awaited()


# ===========================================================================
# Invalid input (tests 14–16)
# ===========================================================================


@pytest.mark.asyncio
async def test_invalid_input_sends_error_message():
    """Unrecognised input -> send_text_message() called with LANGUAGE_NOT_RECOGNISED_MESSAGE."""
    redis = _mock_redis()
    payload = _make_payload(body="xyz123")
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=None,
        ),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock) as mock_send,
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        # Find the call that sent LANGUAGE_NOT_RECOGNISED_MESSAGE
        error_calls = [
            c for c in mock_send.call_args_list if c[0][1] == LANGUAGE_NOT_RECOGNISED_MESSAGE
        ]
        assert len(error_calls) == 1
        assert error_calls[0][0][0] == PHONE


@pytest.mark.asyncio
async def test_invalid_input_resends_language_selection():
    """Unrecognised input -> send_language_selection() called."""
    redis = _mock_redis()
    payload = _make_payload(body="xyz123")
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=None,
        ),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch(
            "backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock
        ) as mock_sel,
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        mock_sel.assert_awaited_once_with(PHONE)


@pytest.mark.asyncio
async def test_invalid_input_does_not_change_session():
    """Unrecognised input -> _save_session() NOT called."""
    redis = _mock_redis()
    payload = _make_payload(body="xyz123")
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=None,
        ),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
    ):
        await _handle_language_state(payload, session, REQUEST_ID, redis)

        mock_save.assert_not_awaited()


# ===========================================================================
# Error propagation (tests 17–18)
# ===========================================================================


@pytest.mark.asyncio
async def test_language_propagates_send_error():
    """If send_text_message() raises, exception propagates."""
    redis = _mock_redis()
    payload = _make_payload(body="1")
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=("Hindi", "hi"),
        ),
        patch(
            "backend.app.api.webhooks.send_text_message",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Twilio down"),
        ),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
    ):
        with pytest.raises(RuntimeError, match="Twilio down"):
            await _handle_language_state(payload, session, REQUEST_ID, redis)


@pytest.mark.asyncio
async def test_language_propagates_selection_error():
    """If send_language_selection() raises on invalid input, exception propagates."""
    redis = _mock_redis()
    payload = _make_payload(body="xyz123")
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.parse_language_selection",
            return_value=None,
        ),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch(
            "backend.app.api.webhooks.send_language_selection",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Language menu failed"),
        ),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
    ):
        with pytest.raises(RuntimeError, match="Language menu failed"):
            await _handle_language_state(payload, session, REQUEST_ID, redis)


# ===========================================================================
# Logging (tests 19–20)
# ===========================================================================


@pytest.mark.asyncio
async def test_language_logs_with_request_id():
    """Handler logs include request_id in context."""
    redis = _mock_redis()
    payload = _make_payload(body="1")
    session = _make_session()

    log_output = StringIO()
    handler_id = logger.add(
        log_output,
        format="{extra} {message}",
        level="DEBUG",
        filter=lambda r: "request_id" in r["extra"],
    )
    try:
        with (
            patch(
                "backend.app.api.webhooks.parse_language_selection",
                return_value=("Hindi", "hi"),
            ),
            patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
            patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
        ):
            await _handle_language_state(payload, session, REQUEST_ID, redis)

        log_text = log_output.getvalue()
        assert REQUEST_ID in log_text
    finally:
        logger.remove(handler_id)


@pytest.mark.asyncio
async def test_language_logs_no_raw_phone():
    """Log output does not contain raw phone numbers."""
    redis = _mock_redis()
    payload = _make_payload(body="1")
    session = _make_session()

    log_output = StringIO()
    handler_id = logger.add(
        log_output,
        format="{extra} {message}",
        level="DEBUG",
    )
    try:
        with (
            patch(
                "backend.app.api.webhooks.parse_language_selection",
                return_value=("Hindi", "hi"),
            ),
            patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
            patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
        ):
            await _handle_language_state(payload, session, REQUEST_ID, redis)

        log_text = log_output.getvalue()
        # Raw phone number should NOT appear in logs
        assert "919876543210" not in log_text
        assert PHONE not in log_text
    finally:
        logger.remove(handler_id)
