"""S4.5 — Image State tests.

20 tests covering _handle_image_state(): PROCESSING_ACK_MESSAGE,
NO_IMAGE_MESSAGE, UNSUPPORTED_MEDIA_MESSAGE constants, valid image path
(ack, session update, field preservation, pipeline call, cleanup),
no-media path, non-image media path, error propagation, and PHI-safe logging.
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
    NO_IMAGE_MESSAGE,
    PROCESSING_ACK_MESSAGE,
    UNSUPPORTED_MEDIA_MESSAGE,
    _handle_image_state,
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
REQUEST_ID = "req-image-test-001"
CREATED_AT = "2026-03-01T10:00:00+00:00"
MEDIA_URL = "https://api.twilio.com/media/img123"


def _make_payload(**overrides) -> WebhookPayload:
    defaults = {
        "from_number": PHONE,
        "body": "",
        "num_media": 1,
        "media_url": MEDIA_URL,
        "media_content_type": "image/jpeg",
    }
    defaults.update(overrides)
    return WebhookPayload(**defaults)


def _make_session(**overrides) -> SessionState:
    defaults = {
        "status": SessionStatus.WAITING_FOR_IMAGE,
        "language_code": "hi",
        "language_name": "Hindi",
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
# Constants (tests 1–5)
# ===========================================================================


def test_processing_ack_message_exists():
    """PROCESSING_ACK_MESSAGE is importable from backend.app.api.webhooks."""
    assert PROCESSING_ACK_MESSAGE is not None
    assert isinstance(PROCESSING_ACK_MESSAGE, str)
    assert len(PROCESSING_ACK_MESSAGE) > 0


def test_processing_ack_message_mentions_wait():
    """PROCESSING_ACK_MESSAGE mentions wait time or 'please wait'."""
    lower = PROCESSING_ACK_MESSAGE.lower()
    assert "wait" in lower or "20" in lower or "30" in lower or "moment" in lower


def test_no_image_message_exists():
    """NO_IMAGE_MESSAGE is importable and non-empty."""
    assert NO_IMAGE_MESSAGE is not None
    assert isinstance(NO_IMAGE_MESSAGE, str)
    assert len(NO_IMAGE_MESSAGE) > 0


def test_no_image_message_mentions_photo():
    """NO_IMAGE_MESSAGE mentions photo or prescription image."""
    lower = NO_IMAGE_MESSAGE.lower()
    assert "photo" in lower or "image" in lower or "prescription" in lower


def test_unsupported_media_message_exists():
    """UNSUPPORTED_MEDIA_MESSAGE is importable and non-empty."""
    assert UNSUPPORTED_MEDIA_MESSAGE is not None
    assert isinstance(UNSUPPORTED_MEDIA_MESSAGE, str)
    assert len(UNSUPPORTED_MEDIA_MESSAGE) > 0


# ===========================================================================
# Valid image — acknowledgement & session (tests 6–11)
# ===========================================================================


@pytest.mark.asyncio
async def test_valid_image_sends_ack():
    """Valid image payload -> send_text_message() called with PROCESSING_ACK_MESSAGE."""
    redis = _mock_redis()
    payload = _make_payload()
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock) as mock_send,
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._delete_session", new_callable=AsyncMock),
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        # Find the call that sent PROCESSING_ACK_MESSAGE
        ack_calls = [c for c in mock_send.call_args_list if c[0][1] == PROCESSING_ACK_MESSAGE]
        assert len(ack_calls) == 1
        assert ack_calls[0][0][0] == PHONE


@pytest.mark.asyncio
async def test_valid_image_updates_session_to_processing():
    """Valid image -> session saved with status=PROCESSING."""
    redis = _mock_redis()
    payload = _make_payload()
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
        patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._delete_session", new_callable=AsyncMock),
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        mock_save.assert_awaited_once()
        saved_session = mock_save.call_args[0][1]
        assert saved_session.status == SessionStatus.PROCESSING


@pytest.mark.asyncio
async def test_valid_image_preserves_language_code():
    """Updated session retains language_code from original session."""
    redis = _mock_redis()
    payload = _make_payload()
    session = _make_session(language_code="bn")

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
        patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._delete_session", new_callable=AsyncMock),
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        saved_session = mock_save.call_args[0][1]
        assert saved_session.language_code == "bn"


@pytest.mark.asyncio
async def test_valid_image_preserves_language_name():
    """Updated session retains language_name from original session."""
    redis = _mock_redis()
    payload = _make_payload()
    session = _make_session(language_name="Bengali")

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
        patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._delete_session", new_callable=AsyncMock),
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        saved_session = mock_save.call_args[0][1]
        assert saved_session.language_name == "Bengali"


@pytest.mark.asyncio
async def test_valid_image_preserves_request_id():
    """Updated session retains request_id from original session."""
    redis = _mock_redis()
    payload = _make_payload()
    session = _make_session(request_id="original-req-id-777")

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
        patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._delete_session", new_callable=AsyncMock),
    ):
        await _handle_image_state(payload, session, "original-req-id-777", redis)

        saved_session = mock_save.call_args[0][1]
        assert saved_session.request_id == "original-req-id-777"


@pytest.mark.asyncio
async def test_valid_image_preserves_created_at():
    """Updated session retains created_at from original session."""
    redis = _mock_redis()
    payload = _make_payload()
    original_ts = "2026-01-15T08:30:00+00:00"
    session = _make_session(created_at=original_ts)

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
        patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._delete_session", new_callable=AsyncMock),
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        saved_session = mock_save.call_args[0][1]
        assert saved_session.created_at == original_ts


# ===========================================================================
# Valid image — pipeline placeholder (tests 12–13)
# ===========================================================================


@pytest.mark.asyncio
async def test_valid_image_calls_pipeline_placeholder():
    """Valid image -> _run_pipeline() is called with correct args."""
    redis = _mock_redis()
    payload = _make_payload()
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock) as mock_pipeline,
        patch("backend.app.api.webhooks._delete_session", new_callable=AsyncMock),
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        mock_pipeline.assert_awaited_once()
        call_args = mock_pipeline.call_args
        assert call_args[0][0] == payload  # first arg: payload
        assert call_args[0][2] == REQUEST_ID  # third arg: request_id
        assert call_args[0][3] is redis  # fourth arg: redis


@pytest.mark.asyncio
async def test_valid_image_pipeline_cleans_session():
    """After pipeline runs, session is cleaned up (tested in detail by S10.1)."""
    redis = _mock_redis()
    payload = _make_payload()
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock) as mock_pipeline,
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        # _run_pipeline was called (session cleanup is tested in S10.1 tests)
        mock_pipeline.assert_awaited_once()


# ===========================================================================
# No media attached (tests 14–15)
# ===========================================================================


@pytest.mark.asyncio
async def test_no_media_sends_reminder():
    """num_media=0 -> send_text_message() called with NO_IMAGE_MESSAGE."""
    redis = _mock_redis()
    payload = _make_payload(num_media=0, media_url=None, media_content_type=None, body="Hello")
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock) as mock_send,
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        mock_send.assert_awaited_once_with(PHONE, NO_IMAGE_MESSAGE)


@pytest.mark.asyncio
async def test_no_media_does_not_change_session():
    """num_media=0 -> _save_session() NOT called."""
    redis = _mock_redis()
    payload = _make_payload(num_media=0, media_url=None, media_content_type=None)
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        mock_save.assert_not_awaited()


# ===========================================================================
# Non-image media (tests 16–17)
# ===========================================================================


@pytest.mark.asyncio
async def test_non_image_media_sends_error():
    """num_media=1 with media_content_type='application/pdf' -> UNSUPPORTED_MEDIA_MESSAGE sent."""
    redis = _mock_redis()
    payload = _make_payload(media_content_type="application/pdf")
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock) as mock_send,
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        mock_send.assert_awaited_once_with(PHONE, UNSUPPORTED_MEDIA_MESSAGE)


@pytest.mark.asyncio
async def test_non_image_media_does_not_change_session():
    """Non-image media -> _save_session() NOT called."""
    redis = _mock_redis()
    payload = _make_payload(media_content_type="video/mp4")
    session = _make_session()

    with (
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock) as mock_save,
    ):
        await _handle_image_state(payload, session, REQUEST_ID, redis)

        mock_save.assert_not_awaited()


# ===========================================================================
# Error propagation (test 18)
# ===========================================================================


@pytest.mark.asyncio
async def test_image_propagates_send_error():
    """If send_text_message() raises, exception propagates."""
    redis = _mock_redis()
    payload = _make_payload()
    session = _make_session()

    with (
        patch(
            "backend.app.api.webhooks.send_text_message",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Twilio down"),
        ),
        patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock),
        patch("backend.app.api.webhooks._delete_session", new_callable=AsyncMock),
    ):
        with pytest.raises(RuntimeError, match="Twilio down"):
            await _handle_image_state(payload, session, REQUEST_ID, redis)


# ===========================================================================
# Logging (tests 19–20)
# ===========================================================================


@pytest.mark.asyncio
async def test_image_logs_with_request_id():
    """Handler logs include request_id in context."""
    redis = _mock_redis()
    payload = _make_payload()
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
            patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
            patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
            patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock),
            patch("backend.app.api.webhooks._delete_session", new_callable=AsyncMock),
        ):
            await _handle_image_state(payload, session, REQUEST_ID, redis)

        log_text = log_output.getvalue()
        assert REQUEST_ID in log_text
    finally:
        logger.remove(handler_id)


@pytest.mark.asyncio
async def test_image_logs_no_raw_phone_or_media_url():
    """Log output does not contain raw phone numbers or media URLs."""
    redis = _mock_redis()
    payload = _make_payload()
    session = _make_session()

    log_output = StringIO()
    handler_id = logger.add(
        log_output,
        format="{extra} {message}",
        level="DEBUG",
    )
    try:
        with (
            patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
            patch("backend.app.api.webhooks._save_session", new_callable=AsyncMock),
            patch("backend.app.api.webhooks._run_pipeline", new_callable=AsyncMock),
            patch("backend.app.api.webhooks._delete_session", new_callable=AsyncMock),
        ):
            await _handle_image_state(payload, session, REQUEST_ID, redis)

        log_text = log_output.getvalue()
        # Raw phone number should NOT appear in logs
        assert "919876543210" not in log_text
        assert PHONE not in log_text
        # Media URL should NOT appear in logs
        assert MEDIA_URL not in log_text
    finally:
        logger.remove(handler_id)
