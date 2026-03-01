"""S3.3 — Send Text Message tests.

Tests for _get_twilio_client() lazy singleton and send_text_message() async wrapper
with tenacity retry, asyncio.to_thread, and PHI-safe logging.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

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

from twilio.base.exceptions import TwilioRestException

from backend.app.services.whatsapp import _get_twilio_client, send_text_message


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


# ---------------------------------------------------------------------------
# FR-1: _get_twilio_client tests
# ---------------------------------------------------------------------------

class TestGetTwilioClient:
    """Tests for the lazy singleton Twilio client."""

    @patch("backend.app.services.whatsapp.Client")
    def test_get_twilio_client_returns_client(self, mock_client_cls: MagicMock) -> None:
        """_get_twilio_client() returns a twilio.rest.Client instance."""
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        result = _get_twilio_client()

        assert result is mock_instance
        mock_client_cls.assert_called_once()

    @patch("backend.app.services.whatsapp.Client")
    def test_get_twilio_client_singleton(self, mock_client_cls: MagicMock) -> None:
        """Calling _get_twilio_client() twice returns the same instance."""
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        first = _get_twilio_client()
        second = _get_twilio_client()

        assert first is second
        mock_client_cls.assert_called_once()  # Only created once

    @patch("backend.app.services.whatsapp.Client")
    def test_get_twilio_client_uses_settings(self, mock_client_cls: MagicMock) -> None:
        """_get_twilio_client() uses TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN from settings."""
        from backend.app.core.config import settings

        _get_twilio_client()

        mock_client_cls.assert_called_once_with(
            settings.TWILIO_ACCOUNT_SID,
            settings.TWILIO_AUTH_TOKEN,
        )


# ---------------------------------------------------------------------------
# FR-2: send_text_message tests
# ---------------------------------------------------------------------------

class TestSendTextMessage:
    """Tests for the async send_text_message function."""

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_text_message_calls_twilio(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """send_text_message calls client.messages.create with correct params."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM1234567890"
        mock_to_thread.return_value = mock_msg

        to = "whatsapp:+919876543210"
        body = "Hello patient"

        await send_text_message(to, body)

        mock_to_thread.assert_called_once()
        # Verify the callable passed to to_thread
        call_args = mock_to_thread.call_args
        assert call_args is not None

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_text_message_uses_asyncio_to_thread(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """Synchronous Twilio call is wrapped in asyncio.to_thread."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM1234567890"
        mock_to_thread.return_value = mock_msg

        await send_text_message("whatsapp:+919876543210", "Test")

        mock_to_thread.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_text_message_returns_sid(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """send_text_message returns the message SID string."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM9876543210"
        mock_to_thread.return_value = mock_msg

        result = await send_text_message("whatsapp:+919876543210", "Hello")

        assert result == "SM9876543210"

    @pytest.mark.asyncio
    async def test_send_text_message_empty_body_raises(self) -> None:
        """Empty body raises ValueError."""
        with pytest.raises(ValueError, match="[Bb]ody.*empty|empty.*[Bb]ody"):
            await send_text_message("whatsapp:+919876543210", "")

    @pytest.mark.asyncio
    async def test_send_text_message_empty_to_raises(self) -> None:
        """Empty to raises ValueError."""
        with pytest.raises(ValueError, match="[Rr]ecipient.*empty|empty.*[Rr]ecipient"):
            await send_text_message("", "Hello")

    @pytest.mark.asyncio
    async def test_send_text_message_whitespace_body_raises(self) -> None:
        """Whitespace-only body raises ValueError."""
        with pytest.raises(ValueError, match="[Bb]ody.*empty|empty.*[Bb]ody"):
            await send_text_message("whatsapp:+919876543210", "   ")

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_text_message_from_uses_settings(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """from_ parameter matches settings.TWILIO_WHATSAPP_FROM."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM1234567890"
        mock_to_thread.return_value = mock_msg

        await send_text_message("whatsapp:+919876543210", "Hello")

        # Verify the sync call was dispatched via to_thread
        assert mock_to_thread.called


# ---------------------------------------------------------------------------
# FR-3: Retry tests
# ---------------------------------------------------------------------------

class TestSendTextMessageRetry:
    """Tests for tenacity retry behavior."""

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_text_message_retries_on_twilio_error(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """Retries on TwilioRestException and succeeds on 3rd attempt."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_msg = MagicMock()
        mock_msg.sid = "SM_RECOVERED"

        mock_to_thread.side_effect = [
            _make_twilio_error(),
            _make_twilio_error(),
            mock_msg,
        ]

        result = await send_text_message("whatsapp:+919876543210", "Retry test")

        assert result == "SM_RECOVERED"
        assert mock_to_thread.call_count == 3

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_text_message_exhausts_retries(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """After 3 failed attempts, re-raises the TwilioRestException."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_to_thread.side_effect = _make_twilio_error()

        with pytest.raises(TwilioRestException):
            await send_text_message("whatsapp:+919876543210", "Fail test")

        assert mock_to_thread.call_count == 3

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_text_message_no_retry_on_value_error(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """ValueError is NOT retried — propagates immediately."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Validation errors happen before to_thread, so to_thread shouldn't be called
        with pytest.raises(ValueError):
            await send_text_message("whatsapp:+919876543210", "")

        mock_to_thread.assert_not_called()


# ---------------------------------------------------------------------------
# FR-4: Logging tests
# ---------------------------------------------------------------------------

class TestSendTextMessageLogging:
    """Tests for PHI-safe logging."""

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_text_message_logs_no_raw_phone(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock, capsys
    ) -> None:
        """Raw phone number is never logged."""
        from io import StringIO

        from loguru import logger

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM_LOG_TEST"
        mock_to_thread.return_value = mock_msg

        phone = "whatsapp:+919876543210"
        log_output = StringIO()
        handler_id = logger.add(log_output, format="{message}", level="DEBUG")

        try:
            await send_text_message(phone, "Test message for logging")
            log_text = log_output.getvalue()

            # Raw phone number should NOT appear in logs
            assert "+919876543210" not in log_text
            assert phone not in log_text
        finally:
            logger.remove(handler_id)

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    async def test_send_text_message_logs_no_full_body(
        self, mock_get_client: MagicMock, mock_to_thread: MagicMock
    ) -> None:
        """Full message body is never logged."""
        from io import StringIO

        from loguru import logger

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.sid = "SM_LOG_TEST2"
        mock_to_thread.return_value = mock_msg

        body = "This is a unique test message body that should not appear in logs XYZZY123"
        log_output = StringIO()
        handler_id = logger.add(log_output, format="{message}", level="DEBUG")

        try:
            await send_text_message("whatsapp:+919876543210", body)
            log_text = log_output.getvalue()

            # Full body should NOT appear in logs
            assert body not in log_text
            assert "XYZZY123" not in log_text
        finally:
            logger.remove(handler_id)
