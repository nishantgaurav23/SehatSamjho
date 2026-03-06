"""S14.1 — Edge TTS Fallback Provider Tests.

Tests for edge-tts integration as a Bhashini TTS fallback.
All edge-tts calls are mocked — no network required.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

# Ensure env vars are set before any module-level imports
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-token")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+1234567890")
os.environ.setdefault("BHASHINI_API_KEY", "")
os.environ.setdefault("BHASHINI_USER_ID", "test-user")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


class TestEdgeTTSVoices:
    """FR-2: Voice mapping tests."""

    def test_module_importable(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        assert isinstance(EDGE_TTS_VOICES, dict)

    def test_hindi_voice_exists(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        assert "hi" in EDGE_TTS_VOICES

    def test_tamil_voice_exists(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        assert "ta" in EDGE_TTS_VOICES

    def test_bengali_voice_exists(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        assert "bn" in EDGE_TTS_VOICES

    def test_telugu_voice_exists(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        assert "te" in EDGE_TTS_VOICES

    def test_marathi_voice_exists(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        assert "mr" in EDGE_TTS_VOICES

    def test_gujarati_voice_exists(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        assert "gu" in EDGE_TTS_VOICES

    def test_kannada_voice_exists(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        assert "kn" in EDGE_TTS_VOICES

    def test_malayalam_voice_exists(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        assert "ml" in EDGE_TTS_VOICES

    def test_at_least_10_languages(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        assert len(EDGE_TTS_VOICES) >= 10

    def test_all_voices_are_strings(self):
        from backend.app.services.tts_edge import EDGE_TTS_VOICES

        for code, voice in EDGE_TTS_VOICES.items():
            assert isinstance(voice, str), f"Voice for {code} is not a string"


class TestEdgeTTSError:
    """FR-3: Custom exception."""

    def test_exception_importable(self):
        from backend.app.services.tts_edge import EdgeTTSError

        assert issubclass(EdgeTTSError, Exception)

    def test_exception_message(self):
        from backend.app.services.tts_edge import EdgeTTSError

        exc = EdgeTTSError("test error")
        assert str(exc) == "test error"


class TestEdgeTextToSpeech:
    """FR-3: edge_text_to_speech() function."""

    @pytest.mark.asyncio
    async def test_function_importable(self):
        from backend.app.services.tts_edge import edge_text_to_speech

        assert callable(edge_text_to_speech)

    @pytest.mark.asyncio
    async def test_happy_path_returns_bytes(self):
        from backend.app.services.tts_edge import edge_text_to_speech

        fake_audio = b"\xff\xfb\x90\x00" * 100  # fake MP3 bytes

        mock_communicate = MagicMock()

        # edge-tts Communicate.save() writes to a file
        # We mock the stream method instead
        async def fake_stream():
            yield {"type": "audio", "data": fake_audio}

        mock_communicate.stream = fake_stream

        with patch(
            "backend.app.services.tts_edge.edge_tts.Communicate", return_value=mock_communicate
        ):
            result = await edge_text_to_speech("Hello world", "hi", request_id="test-123")

        assert isinstance(result, bytes)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_empty_text_raises_value_error(self):
        from backend.app.services.tts_edge import edge_text_to_speech

        with pytest.raises(ValueError, match="text must be"):
            await edge_text_to_speech("", "hi")

    @pytest.mark.asyncio
    async def test_empty_language_raises_value_error(self):
        from backend.app.services.tts_edge import edge_text_to_speech

        with pytest.raises(ValueError, match="language_code must be"):
            await edge_text_to_speech("Hello", "")

    @pytest.mark.asyncio
    async def test_unsupported_language_raises_edge_tts_error(self):
        from backend.app.services.tts_edge import EdgeTTSError, edge_text_to_speech

        with pytest.raises(EdgeTTSError, match="not supported"):
            await edge_text_to_speech("Hello", "xx")

    @pytest.mark.asyncio
    async def test_edge_tts_failure_raises_error(self):
        from backend.app.services.tts_edge import EdgeTTSError, edge_text_to_speech

        mock_communicate = MagicMock()

        async def fake_stream():
            raise Exception("Network error")
            yield  # noqa: F841 - unreachable yield makes this an async generator

        mock_communicate.stream = fake_stream

        with patch(
            "backend.app.services.tts_edge.edge_tts.Communicate", return_value=mock_communicate
        ):
            with pytest.raises(EdgeTTSError):
                await edge_text_to_speech("Hello", "hi", request_id="test-err")

    @pytest.mark.asyncio
    async def test_empty_audio_raises_error(self):
        from backend.app.services.tts_edge import EdgeTTSError, edge_text_to_speech

        mock_communicate = MagicMock()

        async def fake_stream():
            # Yield no audio data
            yield {"type": "metadata", "data": None}

        mock_communicate.stream = fake_stream

        with patch(
            "backend.app.services.tts_edge.edge_tts.Communicate", return_value=mock_communicate
        ):
            with pytest.raises(EdgeTTSError, match="empty audio"):
                await edge_text_to_speech("Hello", "hi")


class TestGetVoiceForLanguage:
    """FR-2: get_voice_for_language helper."""

    def test_returns_voice_for_hindi(self):
        from backend.app.services.tts_edge import get_voice_for_language

        voice = get_voice_for_language("hi")
        assert voice is not None
        assert "hi-IN" in voice or "Hindi" in voice

    def test_returns_none_for_unsupported(self):
        from backend.app.services.tts_edge import get_voice_for_language

        voice = get_voice_for_language("xx")
        assert voice is None
