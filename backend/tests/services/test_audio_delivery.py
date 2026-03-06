"""Tests for S9.4 — Audio Delivery Orchestrator (generate_and_deliver_audio).

20 tests covering: import, async, signature, happy path, input validation,
error propagation, logging, and request_id forwarding.

All downstream calls (_get_audio_bytes, _upload_to_s3) are mocked.
"""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Test 1: Importability
# ---------------------------------------------------------------------------


class TestImport:
    """Tests 1–3: import, async, signature."""

    def test_import(self):
        """generate_and_deliver_audio is importable from backend.app.services.tts."""
        from backend.app.services.tts import generate_and_deliver_audio

        assert generate_and_deliver_audio is not None

    def test_is_async(self):
        """generate_and_deliver_audio is a coroutine function."""
        from backend.app.services.tts import generate_and_deliver_audio

        assert asyncio.iscoroutinefunction(generate_and_deliver_audio)

    def test_signature(self):
        """Accepts text, language_code, request_id params with correct defaults."""
        from backend.app.services.tts import generate_and_deliver_audio

        sig = inspect.signature(generate_and_deliver_audio)
        params = list(sig.parameters.keys())
        assert "text" in params
        assert "language_code" in params
        assert "request_id" in params
        assert sig.parameters["request_id"].default == ""


# ---------------------------------------------------------------------------
# Tests 4–7: Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHappyPath:
    """Tests 4–7: orchestration happy path."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_happy_path(self, mock_get_audio, mock_s3):
        """Returns presigned URL from S3 on success."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (b"audio-bytes", "audio/ogg")
        mock_s3.return_value = "https://s3.amazonaws.com/bucket/audio/test.ogg"

        result = await generate_and_deliver_audio("hello", "hi", request_id="req-1")

        assert result == "https://s3.amazonaws.com/bucket/audio/test.ogg"

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_calls_get_audio_with_correct_args(self, mock_get_audio, mock_s3):
        """_get_audio_bytes called with text, language_code, request_id."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (b"audio-bytes", "audio/ogg")
        mock_s3.return_value = "https://example.com/audio.ogg"

        await generate_and_deliver_audio("hello world", "ta", request_id="req-2")

        mock_get_audio.assert_awaited_once_with("hello world", "ta", "req-2")

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_calls_s3_with_audio_output(self, mock_get_audio, mock_s3):
        """_upload_to_s3 called with audio bytes + correct extension and content type."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (b"tts-output-bytes", "audio/ogg")
        mock_s3.return_value = "https://example.com/audio.ogg"

        await generate_and_deliver_audio("test", "hi", request_id="req-3")

        mock_s3.assert_awaited_once_with(
            b"tts-output-bytes", request_id="req-3", extension=".ogg", content_type="audio/ogg"
        )

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_returns_presigned_url(self, mock_get_audio, mock_s3):
        """Return value is exactly the string from _upload_to_s3."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (b"audio", "audio/ogg")
        expected_url = "https://s3.ap-south-1.amazonaws.com/bucket/audio/abc.ogg?sig=xyz"
        mock_s3.return_value = expected_url

        result = await generate_and_deliver_audio("text", "hi")

        assert result is expected_url


# ---------------------------------------------------------------------------
# Tests 8–12: Input validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestInputValidation:
    """Tests 8–12: empty/whitespace text and language_code validation."""

    async def test_empty_text_raises_valueerror(self):
        """Empty string text raises ValueError."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError, match="text"):
            await generate_and_deliver_audio("", "hi")

    async def test_whitespace_text_raises_valueerror(self):
        """Whitespace-only text raises ValueError."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError, match="text"):
            await generate_and_deliver_audio("   \t\n  ", "hi")

    async def test_empty_language_code_raises_valueerror(self):
        """Empty language_code raises ValueError."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError, match="language_code"):
            await generate_and_deliver_audio("hello", "")

    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_valueerror_skips_tts(self, mock_get_audio):
        """On ValueError, _get_audio_bytes is never called."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError):
            await generate_and_deliver_audio("", "hi")

        mock_get_audio.assert_not_awaited()

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    async def test_valueerror_skips_s3(self, mock_s3):
        """On ValueError, _upload_to_s3 is never called."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError):
            await generate_and_deliver_audio("", "hi")

        mock_s3.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests 13–15: Error propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrorPropagation:
    """Tests 13–15: downstream errors propagate to caller."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_all_tts_failure_returns_none(self, mock_get_audio, mock_s3):
        """When _get_audio_bytes returns (None, None), returns None."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (None, None)

        result = await generate_and_deliver_audio("hello", "hi", request_id="req-err")
        assert result is None

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_tts_failure_skips_s3(self, mock_get_audio, mock_s3):
        """If all TTS fails, _upload_to_s3 is never called."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (None, None)

        await generate_and_deliver_audio("hello", "hi")

        mock_s3.assert_not_awaited()

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_s3_error_returns_none(self, mock_get_audio, mock_s3):
        """S3UploadError from S3 upload returns None (graceful degradation)."""
        from backend.app.services.tts import S3UploadError, generate_and_deliver_audio

        mock_get_audio.return_value = (b"audio-bytes", "audio/ogg")
        mock_s3.side_effect = S3UploadError("S3 failed")

        result = await generate_and_deliver_audio("hello", "hi", request_id="req-s3")
        assert result is None


# ---------------------------------------------------------------------------
# Tests 16–18: Logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestLogging:
    """Tests 16–18: log lines at start, after TTS, and final success."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_logs_start(self, mock_get_audio, mock_s3, capfd):
        """Log line at start includes request_id, language, text_length."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (b"audio", "audio/ogg")
        mock_s3.return_value = "https://example.com/audio.ogg"

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello world", "hi", request_id="req-log1")

            # First info call should be start log
            start_call = mock_logger.info.call_args_list[0]
            log_msg = start_call[0][0]
            assert "request_id" in log_msg.lower() or "req-log1" in str(start_call)
            assert "text_length" in log_msg.lower() or "11" in str(start_call)
            assert "language" in log_msg.lower() or "hi" in str(start_call)

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_logs_audio_available(self, mock_get_audio, mock_s3):
        """Log line after TTS success."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (b"x" * 500, "audio/ogg")
        mock_s3.return_value = "https://example.com/audio.ogg"

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello", "hi", request_id="req-log2")

            assert mock_logger.info.call_count >= 2

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_logs_final_success(self, mock_get_audio, mock_s3):
        """Final log line includes request_id, url_length, latency_ms."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (b"audio", "audio/ogg")
        url = "https://s3.amazonaws.com/bucket/audio/file.ogg?sig=abc123"
        mock_s3.return_value = url

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello", "hi", request_id="req-log3")

            all_calls = mock_logger.info.call_args_list
            final_call = all_calls[-1]
            final_msg = final_call[0][0]
            assert "latency_ms" in final_msg.lower() or "latency" in final_msg.lower()
            assert "url_length" in final_msg.lower() or str(len(url)) in str(final_call)


# ---------------------------------------------------------------------------
# Tests 19–20: request_id forwarding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestRequestId:
    """Tests 19–20: request_id passed through and empty request_id works."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_request_id_passed_through(self, mock_get_audio, mock_s3):
        """request_id forwarded to both _get_audio_bytes and S3 calls."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (b"audio", "audio/ogg")
        mock_s3.return_value = "https://example.com/audio.ogg"

        await generate_and_deliver_audio("hello", "hi", request_id="unique-req-42")

        # Verify _get_audio_bytes received request_id
        call_args = mock_get_audio.call_args[0]
        assert "unique-req-42" in call_args

        # Verify S3 received request_id
        s3_kwargs = mock_s3.call_args
        assert s3_kwargs[1].get("request_id") == "unique-req-42"

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts._get_audio_bytes", new_callable=AsyncMock)
    async def test_empty_request_id_works(self, mock_get_audio, mock_s3):
        """Empty request_id does not raise — functions still called."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_get_audio.return_value = (b"audio", "audio/ogg")
        mock_s3.return_value = "https://example.com/audio.ogg"

        result = await generate_and_deliver_audio("hello", "hi", request_id="")

        assert result == "https://example.com/audio.ogg"
        mock_get_audio.assert_awaited_once()
        mock_s3.assert_awaited_once()
