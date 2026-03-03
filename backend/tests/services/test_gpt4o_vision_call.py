"""Tests for S5.3 — GPT-4O Vision Call.

24 tests covering:
- 4 constant tests (pure, no mocking)
- 5 _encode_image_base64() tests (pure, no mocking)
- 4 _download_image() tests (mock httpx)
- 11 _call_gpt4o_vision() tests (mock _download_image + _get_client)
"""

from __future__ import annotations

import base64
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Set env vars before any app imports
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/testdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")

from backend.app.services.extraction import (
    GPT4O_IMAGE_DETAIL,
    GPT4O_MAX_TOKENS,
    GPT4O_MODEL,
    GPT4O_TEMPERATURE,
    _download_image,
    _encode_image_base64,
    _call_gpt4o_vision,
)


# ===========================================================================
# Constants tests (pure, no mocking)
# ===========================================================================


class TestGPT4OConstants:
    """Tests 1-4: Module-level constants for GPT-4O call parameters."""

    def test_gpt4o_model_constant(self):
        """GPT4O_MODEL equals 'gpt-4o'."""
        assert GPT4O_MODEL == "gpt-4o"

    def test_gpt4o_max_tokens_constant(self):
        """GPT4O_MAX_TOKENS equals 1024."""
        assert GPT4O_MAX_TOKENS == 1024

    def test_gpt4o_temperature_constant(self):
        """GPT4O_TEMPERATURE equals 0.1."""
        assert GPT4O_TEMPERATURE == 0.1

    def test_gpt4o_image_detail_constant(self):
        """GPT4O_IMAGE_DETAIL equals 'high'."""
        assert GPT4O_IMAGE_DETAIL == "high"


# ===========================================================================
# _encode_image_base64() tests (pure, no mocking)
# ===========================================================================


class TestEncodeImageBase64:
    """Tests 5-9: Pure base64 encoding function."""

    def test_encode_image_base64_returns_string(self):
        """Returns a str."""
        result = _encode_image_base64(b"fake-image-bytes")
        assert isinstance(result, str)

    def test_encode_image_base64_default_content_type(self):
        """Output starts with data:image/jpeg;base64, by default."""
        result = _encode_image_base64(b"fake-image-bytes")
        assert result.startswith("data:image/jpeg;base64,")

    def test_encode_image_base64_custom_content_type(self):
        """Passing image/png produces data:image/png;base64, prefix."""
        result = _encode_image_base64(b"fake-image-bytes", content_type="image/png")
        assert result.startswith("data:image/png;base64,")

    def test_encode_image_base64_correct_encoding(self):
        """Base64-decoding the payload matches original bytes."""
        original = b"prescription-image-content-12345"
        result = _encode_image_base64(original)
        # Extract base64 payload after the comma
        payload = result.split(",", 1)[1]
        decoded = base64.b64decode(payload)
        assert decoded == original

    def test_encode_image_base64_empty_bytes(self):
        """Returns data URI with empty payload for empty input."""
        result = _encode_image_base64(b"")
        assert result == "data:image/jpeg;base64,"


# ===========================================================================
# _download_image() tests (mock httpx)
# ===========================================================================


class TestDownloadImage:
    """Tests 10-13: Async image download with httpx."""

    @pytest.mark.asyncio
    async def test_download_image_success(self):
        """Mocked httpx returns 200 with bytes — function returns those bytes."""
        fake_bytes = b"fake-jpeg-data"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = fake_bytes
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.app.services.extraction.httpx.AsyncClient", return_value=mock_client):
            result = await _download_image("https://api.twilio.com/image.jpg")

        assert result == fake_bytes

    @pytest.mark.asyncio
    async def test_download_image_raises_on_non_2xx(self):
        """Mocked httpx returns 404 — raises httpx.HTTPStatusError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=mock_response,
            )
        )

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.app.services.extraction.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await _download_image("https://api.twilio.com/image.jpg")

    @pytest.mark.asyncio
    async def test_download_image_timeout(self):
        """Mocked httpx raises TimeoutException — propagated."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("backend.app.services.extraction.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.TimeoutException):
                await _download_image("https://api.twilio.com/image.jpg")

    @pytest.mark.asyncio
    async def test_download_image_uses_async_client(self):
        """Verifies httpx.AsyncClient is used (not sync Client)."""
        fake_bytes = b"image-data"
        mock_response = MagicMock()
        mock_response.content = fake_bytes
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "backend.app.services.extraction.httpx.AsyncClient", return_value=mock_client
        ) as mock_cls:
            await _download_image("https://api.twilio.com/image.jpg")
            mock_cls.assert_called_once()


# ===========================================================================
# _call_gpt4o_vision() tests (mock _download_image + _get_client)
# ===========================================================================


def _make_mock_openai_response(content: str = '{"medicines": []}') -> MagicMock:
    """Build a mock ChatCompletion response with a single choice."""
    message = MagicMock()
    message.content = content

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


def _make_mock_openai_response_no_choices() -> MagicMock:
    """Build a mock ChatCompletion response with no choices."""
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 0

    response = MagicMock()
    response.choices = []
    response.usage = usage
    return response


class TestCallGPT4OVision:
    """Tests 14-24: Orchestrating the GPT-4O Vision API call."""

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_returns_string(self):
        """Returns a string from mocked response."""
        mock_response = _make_mock_openai_response('{"doc_type": "prescription"}')
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image",
            ),
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            result = await _call_gpt4o_vision("https://example.com/image.jpg")

        assert isinstance(result, str)
        assert result == '{"doc_type": "prescription"}'

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_calls_download(self):
        """Verifies _download_image is called with the image URL."""
        mock_response = _make_mock_openai_response()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image",
            ) as mock_download,
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            await _call_gpt4o_vision("https://example.com/rx.jpg")

        mock_download.assert_awaited_once_with("https://example.com/rx.jpg")

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_calls_openai(self):
        """Verifies client.chat.completions.create is called."""
        mock_response = _make_mock_openai_response()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image",
            ),
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            await _call_gpt4o_vision("https://example.com/rx.jpg")

        mock_client.chat.completions.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_model_param(self):
        """OpenAI call uses model='gpt-4o'."""
        mock_response = _make_mock_openai_response()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image",
            ),
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            await _call_gpt4o_vision("https://example.com/rx.jpg")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_max_tokens_param(self):
        """OpenAI call uses max_tokens=1024."""
        mock_response = _make_mock_openai_response()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image",
            ),
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            await _call_gpt4o_vision("https://example.com/rx.jpg")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["max_tokens"] == 1024

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_temperature_param(self):
        """OpenAI call uses temperature=0.1."""
        mock_response = _make_mock_openai_response()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image",
            ),
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            await _call_gpt4o_vision("https://example.com/rx.jpg")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_messages_structure(self):
        """Messages list has system message + user message with image_url block."""
        mock_response = _make_mock_openai_response()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image",
            ),
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            await _call_gpt4o_vision("https://example.com/rx.jpg")

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]

        # First message is system
        assert messages[0]["role"] == "system"

        # Last message is user with content list
        user_msg = messages[-1]
        assert user_msg["role"] == "user"
        assert isinstance(user_msg["content"], list)

        # User content has image_url block
        content_types = [block["type"] for block in user_msg["content"]]
        assert "image_url" in content_types

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_image_detail_high(self):
        """image_url block has detail='high'."""
        mock_response = _make_mock_openai_response()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image",
            ),
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            await _call_gpt4o_vision("https://example.com/rx.jpg")

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_msg = messages[-1]

        # Find the image_url block
        image_block = next(b for b in user_msg["content"] if b["type"] == "image_url")
        assert image_block["image_url"]["detail"] == "high"

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_user_text_block(self):
        """User message includes text content block."""
        mock_response = _make_mock_openai_response()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image",
            ),
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            await _call_gpt4o_vision("https://example.com/rx.jpg")

        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_msg = messages[-1]

        # Find the text block
        text_block = next(b for b in user_msg["content"] if b["type"] == "text")
        assert "Extract" in text_block["text"] or "extract" in text_block["text"].lower()

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_no_choices_raises(self):
        """Response with empty choices raises ValueError."""
        mock_response = _make_mock_openai_response_no_choices()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image",
            ),
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            with pytest.raises(ValueError, match="GPT-4O returned no choices"):
                await _call_gpt4o_vision("https://example.com/rx.jpg")

    @pytest.mark.asyncio
    async def test_call_gpt4o_vision_content_type_forwarded(self):
        """Custom content_type is passed to _encode_image_base64."""
        mock_response = _make_mock_openai_response()
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with (
            patch(
                "backend.app.services.extraction._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-png-image",
            ),
            patch(
                "backend.app.services.extraction._get_client",
                return_value=mock_client,
            ),
        ):
            await _call_gpt4o_vision("https://example.com/rx.png", content_type="image/png")

        # Check the image_url in the messages contains the png data URI prefix
        call_kwargs = mock_client.chat.completions.create.call_args
        messages = call_kwargs.kwargs["messages"]
        user_msg = messages[-1]
        image_block = next(b for b in user_msg["content"] if b["type"] == "image_url")
        assert image_block["image_url"]["url"].startswith("data:image/png;base64,")
