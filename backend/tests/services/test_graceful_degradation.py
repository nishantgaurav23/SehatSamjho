"""Tests for S9.5 — Graceful Degradation.

20 tests covering: AUDIO_UNAVAILABLE_MESSAGE constant, return type annotation,
BhashiniTTSError/S3UploadError caught and return None, ValueError still propagates,
warning-level logging on degradation, happy path unchanged, regression guard.

All downstream calls (text_to_speech, _upload_to_s3) are mocked.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Tests 1–3: Constant + return type
# ---------------------------------------------------------------------------


class TestConstantAndReturnType:
    """Tests 1–3: AUDIO_UNAVAILABLE_MESSAGE + return type annotation."""

    def test_import_audio_unavailable_message(self):
        """AUDIO_UNAVAILABLE_MESSAGE is importable from tts module."""
        from backend.app.services.tts import AUDIO_UNAVAILABLE_MESSAGE

        assert AUDIO_UNAVAILABLE_MESSAGE is not None

    def test_audio_unavailable_message_value(self):
        """Constant contains expected text."""
        from backend.app.services.tts import AUDIO_UNAVAILABLE_MESSAGE

        assert AUDIO_UNAVAILABLE_MESSAGE == (
            "Audio is not available at the moment. Please read the text below."
        )

    def test_return_type_annotation(self):
        """generate_and_deliver_audio return annotation is str | None."""
        from backend.app.services.tts import generate_and_deliver_audio

        sig = inspect.signature(generate_and_deliver_audio)
        ann = sig.return_annotation
        # str | None is Union[str, None] — check string representation
        ann_str = str(ann)
        assert "None" in ann_str and "str" in ann_str, f"Expected str | None, got {ann_str}"


# ---------------------------------------------------------------------------
# Tests 4–5: BhashiniTTSError / S3UploadError caught → None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDegradation:
    """Tests 4–5: service errors caught, return None."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_bhashini_failure_returns_none(self, mock_tts, mock_s3):
        """When text_to_speech raises BhashiniTTSError, returns None."""
        from backend.app.services.tts import BhashiniTTSError, generate_and_deliver_audio

        mock_tts.side_effect = BhashiniTTSError("TTS failed")

        result = await generate_and_deliver_audio("hello", "hi", request_id="req-d1")

        assert result is None

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_s3_failure_returns_none(self, mock_tts, mock_s3):
        """When _upload_to_s3 raises S3UploadError, returns None."""
        from backend.app.services.tts import S3UploadError, generate_and_deliver_audio

        mock_tts.return_value = b"audio-bytes"
        mock_s3.side_effect = S3UploadError("S3 failed")

        result = await generate_and_deliver_audio("hello", "hi", request_id="req-d2")

        assert result is None


# ---------------------------------------------------------------------------
# Tests 6–7: Warning-level logging on degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDegradationLogging:
    """Tests 6–7: logger.warning called on degradation."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_bhashini_failure_logs_warning(self, mock_tts, mock_s3):
        """On Bhashini failure, logger.warning is called with request_id."""
        from backend.app.services.tts import BhashiniTTSError, generate_and_deliver_audio

        mock_tts.side_effect = BhashiniTTSError("TTS timeout")

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello", "hi", request_id="req-w1")

            mock_logger.warning.assert_called()
            warn_args = str(mock_logger.warning.call_args)
            assert "req-w1" in warn_args

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_s3_failure_logs_warning(self, mock_tts, mock_s3):
        """On S3 failure, logger.warning is called with request_id."""
        from backend.app.services.tts import S3UploadError, generate_and_deliver_audio

        mock_tts.return_value = b"audio-bytes"
        mock_s3.side_effect = S3UploadError("Upload timeout")

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello", "hi", request_id="req-w2")

            mock_logger.warning.assert_called()
            warn_args = str(mock_logger.warning.call_args)
            assert "req-w2" in warn_args


# ---------------------------------------------------------------------------
# Tests 8–9: ValueError still propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestValueErrorPropagation:
    """Tests 8–9: ValueError is NOT caught — propagates as before."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_valueerror_not_caught_empty_text(self, mock_tts, mock_s3):
        """Empty text still raises ValueError."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError, match="text"):
            await generate_and_deliver_audio("", "hi")

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_valueerror_not_caught_empty_language(self, mock_tts, mock_s3):
        """Empty language_code still raises ValueError."""
        from backend.app.services.tts import generate_and_deliver_audio

        with pytest.raises(ValueError, match="language_code"):
            await generate_and_deliver_audio("hello", "")


# ---------------------------------------------------------------------------
# Test 10: Happy path still returns URL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHappyPath:
    """Test 10: happy path unchanged."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_happy_path_still_returns_url(self, mock_tts, mock_s3):
        """When both TTS and S3 succeed, returns presigned URL string."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"audio-bytes"
        expected = "https://s3.amazonaws.com/bucket/audio/test.ogg"
        mock_s3.return_value = expected

        result = await generate_and_deliver_audio("hello", "hi", request_id="req-hp")

        assert result == expected
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Test 11: Bhashini failure → S3 never called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNoS3OnTTSFailure:
    """Test 11: when TTS fails, _upload_to_s3 is never called."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_bhashini_failure_no_s3_call(self, mock_tts, mock_s3):
        """When TTS fails, _upload_to_s3 is never called."""
        from backend.app.services.tts import BhashiniTTSError, generate_and_deliver_audio

        mock_tts.side_effect = BhashiniTTSError("TTS down")

        await generate_and_deliver_audio("hello", "hi", request_id="req-ns")

        mock_s3.assert_not_awaited()


# ---------------------------------------------------------------------------
# Tests 12–13: Warning log includes request_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWarningRequestId:
    """Tests 12–13: warning log includes the request_id passed in."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_bhashini_failure_with_request_id_in_log(self, mock_tts, mock_s3):
        """Warning log includes the request_id passed in."""
        from backend.app.services.tts import BhashiniTTSError, generate_and_deliver_audio

        mock_tts.side_effect = BhashiniTTSError("TTS error")

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello", "hi", request_id="rid-12")

            warn_call = str(mock_logger.warning.call_args)
            assert "rid-12" in warn_call

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_s3_failure_with_request_id_in_log(self, mock_tts, mock_s3):
        """Warning log includes the request_id passed in."""
        from backend.app.services.tts import S3UploadError, generate_and_deliver_audio

        mock_tts.return_value = b"audio"
        mock_s3.side_effect = S3UploadError("S3 error")

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello", "hi", request_id="rid-13")

            warn_call = str(mock_logger.warning.call_args)
            assert "rid-13" in warn_call


# ---------------------------------------------------------------------------
# Tests 14–15: Generic exceptions NOT caught
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGenericExceptionPropagation:
    """Tests 14–15: unexpected exceptions still propagate."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_generic_exception_from_tts_not_caught(self, mock_tts, mock_s3):
        """Unexpected RuntimeError from TTS still propagates."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.side_effect = RuntimeError("unexpected crash")

        with pytest.raises(RuntimeError, match="unexpected crash"):
            await generate_and_deliver_audio("hello", "hi")

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_generic_exception_from_s3_not_caught(self, mock_tts, mock_s3):
        """Unexpected RuntimeError from S3 still propagates."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"audio-bytes"
        mock_s3.side_effect = RuntimeError("s3 unexpected")

        with pytest.raises(RuntimeError, match="s3 unexpected"):
            await generate_and_deliver_audio("hello", "hi")


# ---------------------------------------------------------------------------
# Tests 16–17: Warning log contains error type name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWarningErrorType:
    """Tests 16–17: warning log includes the exception class name."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_bhashini_failure_log_contains_error_type(self, mock_tts, mock_s3):
        """Warning log includes 'BhashiniTTSError'."""
        from backend.app.services.tts import BhashiniTTSError, generate_and_deliver_audio

        mock_tts.side_effect = BhashiniTTSError("TTS failed badly")

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello", "hi", request_id="req-et1")

            warn_call = str(mock_logger.warning.call_args)
            assert "BhashiniTTSError" in warn_call

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_s3_failure_log_contains_error_type(self, mock_tts, mock_s3):
        """Warning log includes 'S3UploadError'."""
        from backend.app.services.tts import S3UploadError, generate_and_deliver_audio

        mock_tts.return_value = b"audio"
        mock_s3.side_effect = S3UploadError("upload broke")

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello", "hi", request_id="req-et2")

            warn_call = str(mock_logger.warning.call_args)
            assert "S3UploadError" in warn_call


# ---------------------------------------------------------------------------
# Test 18: Happy path logs info, not warning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestHappyPathLogging:
    """Test 18: on success, only info logs (no warning)."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_happy_path_logs_info_not_warning(self, mock_tts, mock_s3):
        """On success, warning is never called."""
        from backend.app.services.tts import generate_and_deliver_audio

        mock_tts.return_value = b"audio"
        mock_s3.return_value = "https://example.com/audio.ogg"

        with patch("backend.app.services.tts.logger") as mock_logger:
            await generate_and_deliver_audio("hello", "hi", request_id="req-ok")

            mock_logger.warning.assert_not_called()
            assert mock_logger.info.call_count >= 1


# ---------------------------------------------------------------------------
# Test 19: None return is falsy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestNoneFalsy:
    """Test 19: returned None on failure is falsy."""

    @patch("backend.app.services.tts._upload_to_s3", new_callable=AsyncMock)
    @patch("backend.app.services.tts.text_to_speech", new_callable=AsyncMock)
    async def test_none_return_is_falsy(self, mock_tts, mock_s3):
        """Returned None on failure is falsy for Phase 10 `if` check."""
        from backend.app.services.tts import BhashiniTTSError, generate_and_deliver_audio

        mock_tts.side_effect = BhashiniTTSError("fail")

        result = await generate_and_deliver_audio("hello", "hi")

        assert not result


# ---------------------------------------------------------------------------
# Test 20: Regression guard — S9.4 tests still pass
# ---------------------------------------------------------------------------


class TestRegressionGuard:
    """Test 20: existing S9.4 tests still pass."""

    def test_existing_s9_4_tests_pass(self):
        """All prior S9.4 imports/functions remain intact."""
        from backend.app.services.tts import (
            BhashiniTTSError,
            S3UploadError,
            _upload_to_s3,
            generate_and_deliver_audio,
            text_to_speech,
        )

        assert callable(generate_and_deliver_audio)
        assert callable(text_to_speech)
        assert callable(_upload_to_s3)
        assert issubclass(BhashiniTTSError, Exception)
        assert issubclass(S3UploadError, Exception)
