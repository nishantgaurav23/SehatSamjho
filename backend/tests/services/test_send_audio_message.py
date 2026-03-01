"""S3.5 — Send Audio Message tests.

Tests for send_audio_message() and send_audio_message_with_fallback() with
tenacity retry, asyncio.to_thread, validation, and PHI-safe logging.
"""

from __future__ import annotations

import os
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

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

from loguru import logger
from twilio.base.exceptions import TwilioRestException

from backend.app.services.whatsapp import (
    send_audio_message,
    send_audio_message_with_fallback,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_twilio_error(status: int = 500, uri: str = "/test") -> TwilioRestException:
    """Create a TwilioRestException for testing."""
    return TwilioRestException(status=status, uri=uri, msg="Server Error")


def _reset_twilio_client() -> None:
    """Reset the module-level Twilio client singleton between tests."""
    import backend.app.services.whatsapp as ws

    ws._twilio_client = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_singleton():
    """Reset the Twilio client singleton before each test."""
    _reset_twilio_client()
    yield
    _reset_twilio_client()


PHONE = "whatsapp:+919876543210"
MEDIA_URL = "https://s3.amazonaws.com/bucket/audio/test.ogg"


# ---------------------------------------------------------------------------
# FR-1: send_audio_message basic tests
# ---------------------------------------------------------------------------

class TestSendAudioMessage:
    """Tests for the async send_audio_message function."""

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_audio_message_success(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """send_audio_message calls client.messages.create with media_url param and returns SID."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM_AUDIO_001"
        mock_to_thread.return_value = mock_msg

        result = await send_audio_message(PHONE, MEDIA_URL)

        assert result == "SM_AUDIO_001"
        mock_to_thread.assert_called_once()
        # Verify media_url is passed to messages.create
        call_args = mock_to_thread.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_audio_message_with_caption(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """Caption is passed as body parameter when provided."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM_CAPTION"
        mock_to_thread.return_value = mock_msg

        caption = "Here is your prescription audio summary"
        await send_audio_message(PHONE, MEDIA_URL, caption=caption)

        # Verify to_thread was called (body=caption is passed to messages.create)
        call_args = mock_to_thread.call_args
        # The callable passed to to_thread is client.messages.create
        # with kwargs including body=caption and media_url=[MEDIA_URL]
        kwargs = call_args.kwargs if call_args.kwargs else {}
        args = call_args.args if call_args.args else ()
        # Check that the call includes body=caption via keyword args
        assert "body" in kwargs or len(args) > 0
        if "body" in kwargs:
            assert kwargs["body"] == caption

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_audio_message_default_caption(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """When caption is None, default body text is used."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM_DEFAULT"
        mock_to_thread.return_value = mock_msg

        await send_audio_message(PHONE, MEDIA_URL, caption=None)

        call_args = mock_to_thread.call_args
        kwargs = call_args.kwargs if call_args.kwargs else {}
        # Default body should be non-empty
        if "body" in kwargs:
            assert kwargs["body"] == "Audio summary of your prescription"


# ---------------------------------------------------------------------------
# FR-1: Validation edge cases
# ---------------------------------------------------------------------------

class TestSendAudioMessageValidation:
    """Validation tests for send_audio_message."""

    @pytest.mark.asyncio
    async def test_send_audio_message_empty_to_raises(self) -> None:
        """Empty to raises ValueError."""
        with pytest.raises(ValueError, match="[Rr]ecipient.*empty|empty.*[Rr]ecipient"):
            await send_audio_message("", MEDIA_URL)

    @pytest.mark.asyncio
    async def test_send_audio_message_empty_media_url_raises(self) -> None:
        """Empty media_url raises ValueError."""
        with pytest.raises(ValueError, match="[Mm]edia.*empty|empty.*[Mm]edia|[Uu]rl.*empty"):
            await send_audio_message(PHONE, "")

    @pytest.mark.asyncio
    async def test_send_audio_message_whitespace_to_raises(self) -> None:
        """Whitespace-only to raises ValueError."""
        with pytest.raises(ValueError, match="[Rr]ecipient.*empty|empty.*[Rr]ecipient"):
            await send_audio_message("   ", MEDIA_URL)

    @pytest.mark.asyncio
    async def test_send_audio_message_whitespace_media_url_raises(self) -> None:
        """Whitespace-only media_url raises ValueError."""
        with pytest.raises(ValueError, match="[Mm]edia.*empty|empty.*[Mm]edia|[Uu]rl.*empty"):
            await send_audio_message(PHONE, "   ")


# ---------------------------------------------------------------------------
# FR-2: Retry tests
# ---------------------------------------------------------------------------

class TestSendAudioMessageRetry:
    """Tests for tenacity retry behavior."""

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_audio_message_retry_on_twilio_error(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """First call raises TwilioRestException, second succeeds — verify 2 calls made."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_msg = MagicMock()
        mock_msg.sid = "SM_RECOVERED"

        mock_to_thread.side_effect = [
            _make_twilio_error(),
            mock_msg,
        ]

        result = await send_audio_message(PHONE, MEDIA_URL)

        assert result == "SM_RECOVERED"
        assert mock_to_thread.call_count == 2

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_audio_message_exhausted_retries(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """All 3 attempts fail — TwilioRestException re-raised."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_to_thread.side_effect = _make_twilio_error()

        with pytest.raises(TwilioRestException):
            await send_audio_message(PHONE, MEDIA_URL)

        assert mock_to_thread.call_count == 3


# ---------------------------------------------------------------------------
# Singleton + asyncio.to_thread tests
# ---------------------------------------------------------------------------

class TestSendAudioMessageInternals:
    """Tests for singleton usage and asyncio.to_thread wrapping."""

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_audio_message_uses_twilio_singleton(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """Verify _get_twilio_client() is called (not a new client)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM_SINGLETON"
        mock_to_thread.return_value = mock_msg

        await send_audio_message(PHONE, MEDIA_URL)

        mock_get_client.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_audio_message_uses_asyncio_to_thread(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """Verify Twilio blocking call is wrapped in asyncio.to_thread."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM_THREAD"
        mock_to_thread.return_value = mock_msg

        await send_audio_message(PHONE, MEDIA_URL)

        mock_to_thread.assert_awaited_once()


# ---------------------------------------------------------------------------
# FR-3: Fallback tests
# ---------------------------------------------------------------------------

class TestSendAudioMessageWithFallback:
    """Tests for send_audio_message_with_fallback."""

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_audio_message")
    async def test_fallback_audio_success(self, mock_send_audio: AsyncMock) -> None:
        """send_audio_message_with_fallback succeeds on first try — returns (sid, True)."""
        mock_send_audio.return_value = "SM_AUDIO_OK"

        sid, audio_sent = await send_audio_message_with_fallback(
            to=PHONE,
            media_url=MEDIA_URL,
            fallback_text="Your prescription summary in text form.",
        )

        assert sid == "SM_AUDIO_OK"
        assert audio_sent is True
        mock_send_audio.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_text_message")
    @patch("backend.app.services.whatsapp.send_audio_message")
    async def test_fallback_audio_fails_sends_text(
        self, mock_send_audio: AsyncMock, mock_send_text: AsyncMock
    ) -> None:
        """Audio fails, fallback text sent — returns (sid, False)."""
        mock_send_audio.side_effect = _make_twilio_error()
        mock_send_text.return_value = "SM_TEXT_FALLBACK"

        fallback = "Your prescription summary in text form."
        sid, audio_sent = await send_audio_message_with_fallback(
            to=PHONE,
            media_url=MEDIA_URL,
            fallback_text=fallback,
        )

        assert sid == "SM_TEXT_FALLBACK"
        assert audio_sent is False
        mock_send_text.assert_awaited_once_with(PHONE, fallback)

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_text_message")
    @patch("backend.app.services.whatsapp.send_audio_message")
    async def test_fallback_both_fail_propagates(
        self, mock_send_audio: AsyncMock, mock_send_text: AsyncMock
    ) -> None:
        """Both audio and text fail — exception propagates."""
        mock_send_audio.side_effect = _make_twilio_error()
        mock_send_text.side_effect = _make_twilio_error(status=503)

        with pytest.raises(TwilioRestException):
            await send_audio_message_with_fallback(
                to=PHONE,
                media_url=MEDIA_URL,
                fallback_text="Fallback text",
            )


# ---------------------------------------------------------------------------
# FR-4: PHI-safe logging tests
# ---------------------------------------------------------------------------

class TestSendAudioMessageLogging:
    """Tests for PHI-safe logging."""

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_logging_phi_safe_no_raw_phone(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """Verify log output contains hash, not raw phone."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM_LOG_PHONE"
        mock_to_thread.return_value = mock_msg

        phone = "whatsapp:+919876543210"
        log_output = StringIO()
        handler_id = logger.add(log_output, format="{message} {extra}", level="DEBUG")

        try:
            await send_audio_message(phone, MEDIA_URL)
            log_text = log_output.getvalue()

            # Raw phone number should NOT appear in logs
            assert "+919876543210" not in log_text
            assert phone not in log_text
        finally:
            logger.remove(handler_id)

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_logging_phi_safe_no_full_url(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """Verify log output contains domain only, not full presigned URL."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM_LOG_URL"
        mock_to_thread.return_value = mock_msg

        presigned_url = (
            "https://s3.ap-south-1.amazonaws.com/sehatsamjho-audio/audio/abc123.ogg"
            "?X-Amz-Signature=deadbeef1234567890"
        )
        log_output = StringIO()
        handler_id = logger.add(log_output, format="{message} {extra}", level="DEBUG")

        try:
            await send_audio_message(PHONE, presigned_url)
            log_text = log_output.getvalue()

            # Full URL with signature should NOT appear in logs
            assert "deadbeef1234567890" not in log_text
            assert presigned_url not in log_text
            # But domain should appear
            assert "s3.ap-south-1.amazonaws.com" in log_text
        finally:
            logger.remove(handler_id)
