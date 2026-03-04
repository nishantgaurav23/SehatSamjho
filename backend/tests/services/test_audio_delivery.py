"""Tests for S9.4 — Audio Delivery Orchestrator (generate_and_deliver_audio).

20 tests covering: import, async, signature, happy path, input validation,
error propagation, logging, and request_id forwarding.

All downstream calls (text_to_speech, _upload_to_s3) are mocked.
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
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_happy_path(self, mock_tts, mock_s3):
        """Returns presigned URL from S3 on success."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"audio-bytes"
        mock_s3.return_value = "https://s3.amazonaws.com/bucket/audio/test.ogg"

        result = await generate_and_deliver_audio("hello", "hi", request_id="req-1")

        assert result == "https://s3.amazonaws.com/bucket/audio/test.ogg"

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_calls_tts_with_correct_args(self, mock_tts, mock_s3):
        """text_to_speech called with text, language_code, request_id."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"audio-bytes"
        mock_s3.return_value = "https://example.com/audio.ogg"

        await generate_and_deliver_audio("hello world", "ta", request_id="req-2")

        mock_tts.assert_awaited_once_with("hello world", "ta", request_id="req-2")

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_calls_s3_with_tts_output(self, mock_tts, mock_s3):
        """_upload_to_s3 called with audio bytes from TTS + request_id."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"tts-output-bytes"
        mock_s3.return_value = "https://example.com/audio.ogg"

        await generate_and_deliver_audio("test", "hi", request_id="req-3")

        mock_s3.assert_awaited_once_with(b"tts-output-bytes", request_id="req-3")

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_returns_presigned_url(self, mock_tts, mock_s3):
        """Return value is exactly the string from _upload_to_s3."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"audio"
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

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_empty_text_raises_valueerror(self, mock_tts, mock_s3):
        """Empty string text raises ValueError."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError, match="text"):
            await generate_and_deliver_audio("", "hi")

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_whitespace_text_raises_valueerror(self, mock_tts, mock_s3):
        """Whitespace-only text raises ValueError."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError, match="text"):
            await generate_and_deliver_audio("   \t\n  ", "hi")

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_empty_language_code_raises_valueerror(self, mock_tts, mock_s3):
        """Empty language_code raises ValueError."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError, match="language_code"):
            await generate_and_deliver_audio("hello", "")

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_valueerror_skips_tts(self, mock_tts, mock_s3):
        """On ValueError, text_to_speech is never called."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError):
            await generate_and_deliver_audio("", "hi")

        mock_tts.assert_not_awaited()

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_valueerror_skips_s3(self, mock_tts, mock_s3):
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
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_tts_error_returns_none(self, mock_tts, mock_s3):
        """BhashiniTTSError from TTS returns None (S9.5 graceful degradation)."""
        from backend.app.services.tts import BhashiniTTSError, generate_and_deliver_audio

        mock_tts.side_effect = BhashiniTTSError("TTS failed")

        result = await generate_and_deliver_audio("hello", "hi", request_id="req-err")
        assert result is None

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_tts_error_skips_s3(self, mock_tts, mock_s3):
        """If TTS fails, _upload_to_s3 is never called."""
        from backend.app.services.tts import BhashiniTTSError, generate_and_deliver_audio

        mock_tts.side_effect = BhashiniTTSError("TTS failed")

        await generate_and_deliver_audio("hello", "hi")

        mock_s3.assert_not_awaited()

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_s3_error_returns_none(self, mock_tts, mock_s3):
        """S3UploadError from S3 upload returns None (S9.5 graceful degradation)."""
        from backend.app.services.tts import S3UploadError, generate_and_deliver_audio

        mock_tts.return_value = b"audio-bytes"
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
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_logs_start(self, mock_tts, mock_s3, capfd):
        """Log line at start includes request_id, language, text_length."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"audio"
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
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_logs_tts_success(self, mock_tts, mock_s3):
        """Log line after TTS includes audio size."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"x" * 500
        mock_s3.return_value = "https://example.com/audio.ogg"

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello", "hi", request_id="req-log2")

            # Second info call should log audio bytes
            all_calls = mock_logger.info.call_args_list
            assert len(all_calls) >= 2
            tts_call = all_calls[1]
            assert "audio" in tts_call[0][0].lower() or "500" in str(tts_call)

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_logs_final_success(self, mock_tts, mock_s3):
        """Final log line includes request_id, url_length, latency_ms."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"audio"
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
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_request_id_passed_through(self, mock_tts, mock_s3):
        """request_id forwarded to both TTS and S3 calls."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"audio"
        mock_s3.return_value = "https://example.com/audio.ogg"

        await generate_and_deliver_audio("hello", "hi", request_id="unique-req-42")

        # Verify TTS received request_id
        tts_kwargs = mock_tts.call_args
        assert tts_kwargs[1].get("request_id") == "unique-req-42" or (
            len(tts_kwargs[0]) >= 3 and tts_kwargs[0][2] == "unique-req-42"
        )

        # Verify S3 received request_id
        s3_kwargs = mock_s3.call_args
        assert s3_kwargs[1].get("request_id") == "unique-req-42"

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_empty_request_id_works(self, mock_tts, mock_s3):
        """Empty request_id does not raise — functions still called."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"audio"
        mock_s3.return_value = "https://example.com/audio.ogg"

        result = await generate_and_deliver_audio("hello", "hi", request_id="")

        assert result == "https://example.com/audio.ogg"
        mock_tts.assert_awaited_once()
        mock_s3.assert_awaited_once()
