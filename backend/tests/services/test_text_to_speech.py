"""Tests for S9.2 — text_to_speech() public API."""

from __future__ import annotations

import asyncio
import inspect
import io
from unittest.mock import AsyncMock, patch

import pytest
from loguru import logger

from backend.app.services.tts import BhashiniTTSError


# ---------------------------------------------------------------------------
# Import & Signature Tests
# ---------------------------------------------------------------------------


class TestImportAndSignature:
    """Tests 1–4: import, async, signature, constant."""

    def test_text_to_speech_importable(self):
        from backend.app.services.tts import text_to_speech

        assert text_to_speech is not None

    def test_text_to_speech_is_async(self):
        from backend.app.services.tts import text_to_speech

        assert asyncio.iscoroutinefunction(text_to_speech)

    def test_text_to_speech_signature(self):
        from backend.app.services.tts import text_to_speech

        sig = inspect.signature(text_to_speech)
        params = list(sig.parameters.keys())
        assert "text" in params
        assert "language_code" in params
        assert "request_id" in params

    def test_max_audio_size_constant(self):
        from backend.app.services.tts import MAX_AUDIO_SIZE

        assert MAX_AUDIO_SIZE == 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# Input Validation Tests
# ---------------------------------------------------------------------------


class TestInputValidation:
    """Tests 5–7: empty text, whitespace text, empty language_code."""

    async def test_empty_text_raises_value_error(self):
        from backend.app.services.tts import text_to_speech

        with pytest.raises(ValueError):
            await text_to_speech("", "hi")

    async def test_whitespace_text_raises_value_error(self):
        from backend.app.services.tts import text_to_speech

        with pytest.raises(ValueError):
            await text_to_speech("   ", "hi")

    async def test_empty_language_code_raises_value_error(self):
        from backend.app.services.tts import text_to_speech

        with pytest.raises(ValueError):
            await text_to_speech("hello", "")


# ---------------------------------------------------------------------------
# Happy Path Tests (mocked _call_bhashini)
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Tests 8–11: happy path, correct args, request_id, return type."""

    async def test_happy_path_returns_audio_bytes(self):
        from backend.app.services.tts import text_to_speech

        fake_audio = b"\x00\x01\x02\x03" * 100
        with patch(
            "backend.app.services.tts._call_bhashini",
            new_callable=AsyncMock,
            return_value=fake_audio,
        ):
            result = await text_to_speech("hello world", "hi", request_id="req-1")

        assert result == fake_audio

    async def test_calls_bhashini_with_correct_args(self):
        from backend.app.services.tts import text_to_speech

        fake_audio = b"\x00\x01\x02\x03"
        with patch(
            "backend.app.services.tts._call_bhashini",
            new_callable=AsyncMock,
            return_value=fake_audio,
        ) as mock_call:
            await text_to_speech("some text", "ta", request_id="req-2")

        mock_call.assert_called_once_with("some text", "ta", request_id="req-2")

    async def test_passes_request_id_to_bhashini(self):
        from backend.app.services.tts import text_to_speech

        fake_audio = b"\xff" * 10
        with patch(
            "backend.app.services.tts._call_bhashini",
            new_callable=AsyncMock,
            return_value=fake_audio,
        ) as mock_call:
            await text_to_speech("text", "hi", request_id="my-req-id")

        _, kwargs = mock_call.call_args
        assert kwargs["request_id"] == "my-req-id"

    async def test_returns_bytes_type(self):
        from backend.app.services.tts import text_to_speech

        fake_audio = b"audio-data"
        with patch(
            "backend.app.services.tts._call_bhashini",
            new_callable=AsyncMock,
            return_value=fake_audio,
        ):
            result = await text_to_speech("hello", "hi")

        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# Audio Validation Tests
# ---------------------------------------------------------------------------


class TestAudioValidation:
    """Tests 12–14: empty audio, oversized audio, at-max-size audio."""

    async def test_empty_audio_raises_bhashini_error(self):
        from backend.app.services.tts import text_to_speech

        with patch(
            "backend.app.services.tts._call_bhashini",
            new_callable=AsyncMock,
            return_value=b"",
        ):
            with pytest.raises(BhashiniTTSError):
                await text_to_speech("hello", "hi")

    async def test_oversized_audio_raises_bhashini_error(self):
        from backend.app.services.tts import MAX_AUDIO_SIZE, text_to_speech

        oversized = b"\x00" * (MAX_AUDIO_SIZE + 1)
        with patch(
            "backend.app.services.tts._call_bhashini",
            new_callable=AsyncMock,
            return_value=oversized,
        ):
            with pytest.raises(BhashiniTTSError):
                await text_to_speech("hello", "hi")

    async def test_audio_at_max_size_passes(self):
        from backend.app.services.tts import MAX_AUDIO_SIZE, text_to_speech

        exact = b"\x00" * MAX_AUDIO_SIZE
        with patch(
            "backend.app.services.tts._call_bhashini",
            new_callable=AsyncMock,
            return_value=exact,
        ):
            result = await text_to_speech("hello", "hi")

        assert len(result) == MAX_AUDIO_SIZE


# ---------------------------------------------------------------------------
# Retry Tests
# ---------------------------------------------------------------------------


class TestRetry:
    """Tests 15–19: retry behaviour with tenacity."""

    async def test_retries_on_bhashini_tts_error(self):
        from backend.app.services.tts import text_to_speech

        fake_audio = b"\x01\x02\x03"
        mock = AsyncMock(
            side_effect=[
                BhashiniTTSError("transient error"),
                BhashiniTTSError("transient error"),
                fake_audio,
            ]
        )
        with patch("backend.app.services.tts._call_bhashini", mock):
            result = await text_to_speech("hello", "hi")

        assert result == fake_audio
        assert mock.call_count == 3

    async def test_no_retry_on_value_error(self):
        """ValueError (input validation) must NOT be retried."""
        from backend.app.services.tts import text_to_speech

        with pytest.raises(ValueError):
            await text_to_speech("", "hi")

    async def test_retry_succeeds_on_second_attempt(self):
        from backend.app.services.tts import text_to_speech

        fake_audio = b"ok-audio"
        mock = AsyncMock(side_effect=[BhashiniTTSError("fail once"), fake_audio])
        with patch("backend.app.services.tts._call_bhashini", mock):
            result = await text_to_speech("hello", "hi")

        assert result == fake_audio
        assert mock.call_count == 2

    async def test_retry_exhausted_raises_original(self):
        from backend.app.services.tts import text_to_speech

        mock = AsyncMock(
            side_effect=[
                BhashiniTTSError("fail-1"),
                BhashiniTTSError("fail-2"),
                BhashiniTTSError("fail-3"),
            ]
        )
        with patch("backend.app.services.tts._call_bhashini", mock):
            with pytest.raises(BhashiniTTSError):
                await text_to_speech("hello", "hi")

        assert mock.call_count == 3

    async def test_retry_exponential_backoff(self):
        """Verify the retry decorator uses exponential wait strategy."""
        from backend.app.services.tts import text_to_speech

        # Access the tenacity retry state on the function
        assert hasattr(text_to_speech, "retry")
        retry_obj = text_to_speech.retry
        # Check wait strategy is exponential
        from tenacity import wait_exponential

        assert isinstance(retry_obj.wait, wait_exponential)


# ---------------------------------------------------------------------------
# Logging Tests
# ---------------------------------------------------------------------------


class TestLogging:
    """Tests 20–22: logging with request_id, no PHI, audio size."""

    async def test_logs_request_id(self):
        from backend.app.services.tts import text_to_speech

        fake_audio = b"\x01\x02\x03"
        log_output = io.StringIO()
        handler_id = logger.add(log_output, format="{message}", level="DEBUG")

        try:
            with patch(
                "backend.app.services.tts._call_bhashini",
                new_callable=AsyncMock,
                return_value=fake_audio,
            ):
                await text_to_speech("hello", "hi", request_id="log-test-123")
        finally:
            logger.remove(handler_id)

        logs = log_output.getvalue()
        assert "log-test-123" in logs

    async def test_no_phi_in_logs(self):
        from backend.app.services.tts import text_to_speech

        sensitive_text = "Patient Rajesh takes Metformin 500mg daily"
        fake_audio = b"\x01\x02\x03"
        log_output = io.StringIO()
        handler_id = logger.add(log_output, format="{message}", level="DEBUG")

        try:
            with patch(
                "backend.app.services.tts._call_bhashini",
                new_callable=AsyncMock,
                return_value=fake_audio,
            ):
                await text_to_speech(sensitive_text, "hi", request_id="phi-test")
        finally:
            logger.remove(handler_id)

        logs = log_output.getvalue()
        assert sensitive_text not in logs
        assert "Patient Rajesh" not in logs
        assert "Metformin" not in logs

    async def test_logs_audio_size_on_success(self):
        from backend.app.services.tts import text_to_speech

        fake_audio = b"\x00" * 512
        log_output = io.StringIO()
        handler_id = logger.add(log_output, format="{message}", level="DEBUG")

        try:
            with patch(
                "backend.app.services.tts._call_bhashini",
                new_callable=AsyncMock,
                return_value=fake_audio,
            ):
                await text_to_speech("hello", "hi", request_id="size-test")
        finally:
            logger.remove(handler_id)

        logs = log_output.getvalue()
        assert "512" in logs
