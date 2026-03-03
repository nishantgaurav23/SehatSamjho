"""S5.5 — Tests for extraction error taxonomy + tenacity retry.

20 tests covering:
- 5 exception class tests (pure, no mocking)
- 5 semantic error detection tests (mock GPT-4O response)
- 8 tenacity retry tests (mock OpenAI errors)
- 2 image download error wrapping tests (mock httpx)
"""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest

# Set env vars before any app imports
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/testdb")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

IMAGE_URL = "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/MM456/Media/ME789"


def _make_valid_json(
    doc_type: str = "prescription",
    overall_confidence: float = 0.85,
) -> str:
    """Build a valid PrescriptionData JSON string with customizable fields."""
    return json.dumps(
        {
            "doctor_name": "Dr. Sharma",
            "patient_name": "Patient A",
            "date": "2025-01-15",
            "diagnosis": "Hypertension",
            "medicines": [
                {
                    "medicine_name": "Amlodipine",
                    "dosage": "5mg",
                    "frequency": "Once daily",
                    "duration": "30 days",
                    "instructions": "Take after food",
                    "confidence": 0.95,
                },
            ],
            "overall_confidence": overall_confidence,
            "doc_type": doc_type,
        }
    )


def _make_openai_status_error(
    error_cls: type,
    message: str = "API error",
    status_code: int = 429,
) -> openai.APIStatusError:
    """Instantiate an OpenAI status error with httpx request/response mocks."""
    mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    mock_response = httpx.Response(status_code, request=mock_request)
    return error_cls(message, response=mock_response, body=None)


def _make_openai_connection_error() -> openai.APIConnectionError:
    """Instantiate an APIConnectionError."""
    mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.APIConnectionError(message="Connection error.", request=mock_request)


def _make_openai_timeout_error() -> openai.APITimeoutError:
    """Instantiate an APITimeoutError."""
    mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    return openai.APITimeoutError(request=mock_request)


# ===========================================================================
# Tests 1–5: Exception classes (pure, no mocking)
# ===========================================================================


class TestExceptionClasses:
    """Tests 1–5: Custom extraction exception hierarchy."""

    def test_extraction_error_is_exception(self):
        """Test 1: ExtractionError inherits from Exception."""
        from backend.app.services.extraction import ExtractionError

        assert issubclass(ExtractionError, Exception)

    def test_not_medical_document_error_inherits_extraction_error(self):
        """Test 2: NotMedicalDocumentError is subclass of ExtractionError."""
        from backend.app.services.extraction import (
            ExtractionError,
            NotMedicalDocumentError,
        )

        assert issubclass(NotMedicalDocumentError, ExtractionError)

    def test_image_not_readable_error_inherits_extraction_error(self):
        """Test 3: ImageNotReadableError is subclass of ExtractionError."""
        from backend.app.services.extraction import (
            ExtractionError,
            ImageNotReadableError,
        )

        assert issubclass(ImageNotReadableError, ExtractionError)

    def test_exception_classes_importable(self):
        """Test 4: All three are importable from backend.app.services.extraction."""
        from backend.app.services.extraction import (
            ExtractionError,
            ImageNotReadableError,
            NotMedicalDocumentError,
        )

        assert ExtractionError is not None
        assert NotMedicalDocumentError is not None
        assert ImageNotReadableError is not None

    def test_exception_message_preserved(self):
        """Test 5: Instantiated with a message, str(exc) returns it."""
        from backend.app.services.extraction import (
            ExtractionError,
            ImageNotReadableError,
            NotMedicalDocumentError,
        )

        assert str(ExtractionError("base error")) == "base error"
        assert str(NotMedicalDocumentError("not medical")) == "not medical"
        assert str(ImageNotReadableError("unreadable")) == "unreadable"


# ===========================================================================
# Tests 6–10: Semantic error detection
# ===========================================================================


class TestSemanticErrorDetection:
    """Tests 6–10: extract_prescription raises for doc_type/confidence."""

    @pytest.mark.asyncio
    async def test_raises_not_medical_document_for_doc_type_other(self):
        """Test 6: doc_type='other' raises NotMedicalDocumentError."""
        from backend.app.services.extraction import (
            NotMedicalDocumentError,
            extract_prescription,
        )

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=_make_valid_json(doc_type="other", overall_confidence=0.8),
        ):
            with pytest.raises(NotMedicalDocumentError):
                await extract_prescription(IMAGE_URL)

    @pytest.mark.asyncio
    async def test_raises_image_not_readable_for_low_confidence(self):
        """Test 7: overall_confidence=0.2 raises ImageNotReadableError."""
        from backend.app.services.extraction import (
            ImageNotReadableError,
            extract_prescription,
        )

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=_make_valid_json(doc_type="prescription", overall_confidence=0.2),
        ):
            with pytest.raises(ImageNotReadableError):
                await extract_prescription(IMAGE_URL)

    @pytest.mark.asyncio
    async def test_no_error_for_prescription_doc_type(self):
        """Test 8: doc_type='prescription', confidence=0.8 returns normally."""
        from backend.app.models.schemas import PrescriptionData
        from backend.app.services.extraction import extract_prescription

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=_make_valid_json(doc_type="prescription", overall_confidence=0.8),
        ):
            result = await extract_prescription(IMAGE_URL)

        assert isinstance(result, PrescriptionData)
        assert result.doc_type == "prescription"

    @pytest.mark.asyncio
    async def test_no_error_for_lab_report_doc_type(self):
        """Test 9: doc_type='lab_report', confidence=0.7 returns normally."""
        from backend.app.models.schemas import PrescriptionData
        from backend.app.services.extraction import extract_prescription

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=_make_valid_json(doc_type="lab_report", overall_confidence=0.7),
        ):
            result = await extract_prescription(IMAGE_URL)

        assert isinstance(result, PrescriptionData)
        assert result.doc_type == "lab_report"

    @pytest.mark.asyncio
    async def test_confidence_threshold_boundary(self):
        """Test 10: overall_confidence=0.3 exactly does NOT raise (boundary)."""
        from backend.app.models.schemas import PrescriptionData
        from backend.app.services.extraction import extract_prescription

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=_make_valid_json(doc_type="prescription", overall_confidence=0.3),
        ):
            result = await extract_prescription(IMAGE_URL)

        assert isinstance(result, PrescriptionData)
        assert result.overall_confidence == 0.3


# ===========================================================================
# Tests 11–18: Tenacity retry
# ===========================================================================


def _make_mock_openai_response(content: str = '{"medicines": []}') -> MagicMock:
    """Build a mock ChatCompletion response."""
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


class TestTenacityRetry:
    """Tests 11–18: Retry on transient OpenAI errors, no retry on non-transient."""

    @pytest.mark.asyncio
    async def test_retries_on_rate_limit_error(self):
        """Test 11: RateLimitError twice then success — returns result."""
        from backend.app.services.extraction import _call_gpt4o_vision

        error = _make_openai_status_error(openai.RateLimitError, status_code=429)
        mock_response = _make_mock_openai_response('{"doc_type": "prescription"}')

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[error, error, mock_response])

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
            patch(
                "backend.app.services.extraction._call_gpt4o_vision.retry.wait",
                return_value=0,
            ),
        ):
            result = await _call_gpt4o_vision("https://example.com/rx.jpg")

        assert result == '{"doc_type": "prescription"}'
        assert mock_client.chat.completions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_retries_on_api_timeout_error(self):
        """Test 12: APITimeoutError once then success."""
        from backend.app.services.extraction import _call_gpt4o_vision

        error = _make_openai_timeout_error()
        mock_response = _make_mock_openai_response('{"doc_type": "prescription"}')

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[error, mock_response])

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
            patch(
                "backend.app.services.extraction._call_gpt4o_vision.retry.wait",
                return_value=0,
            ),
        ):
            result = await _call_gpt4o_vision("https://example.com/rx.jpg")

        assert result == '{"doc_type": "prescription"}'
        assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_internal_server_error(self):
        """Test 13: InternalServerError once then success."""
        from backend.app.services.extraction import _call_gpt4o_vision

        error = _make_openai_status_error(openai.InternalServerError, status_code=500)
        mock_response = _make_mock_openai_response('{"doc_type": "prescription"}')

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[error, mock_response])

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
            patch(
                "backend.app.services.extraction._call_gpt4o_vision.retry.wait",
                return_value=0,
            ),
        ):
            result = await _call_gpt4o_vision("https://example.com/rx.jpg")

        assert result == '{"doc_type": "prescription"}'
        assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_api_connection_error(self):
        """Test 14: APIConnectionError once then success."""
        from backend.app.services.extraction import _call_gpt4o_vision

        error = _make_openai_connection_error()
        mock_response = _make_mock_openai_response('{"doc_type": "prescription"}')

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[error, mock_response])

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
            patch(
                "backend.app.services.extraction._call_gpt4o_vision.retry.wait",
                return_value=0,
            ),
        ):
            result = await _call_gpt4o_vision("https://example.com/rx.jpg")

        assert result == '{"doc_type": "prescription"}'
        assert mock_client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_authentication_error(self):
        """Test 15: AuthenticationError propagates immediately (1 call)."""
        from backend.app.services.extraction import _call_gpt4o_vision

        error = _make_openai_status_error(openai.AuthenticationError, status_code=401)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=error)

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
            with pytest.raises(openai.AuthenticationError):
                await _call_gpt4o_vision("https://example.com/rx.jpg")

        assert mock_client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_bad_request_error(self):
        """Test 16: BadRequestError propagates immediately (1 call)."""
        from backend.app.services.extraction import _call_gpt4o_vision

        error = _make_openai_status_error(openai.BadRequestError, status_code=400)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=error)

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
            with pytest.raises(openai.BadRequestError):
                await _call_gpt4o_vision("https://example.com/rx.jpg")

        assert mock_client.chat.completions.create.call_count == 1

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self):
        """Test 17: Always RateLimitError — raises after 3 attempts."""
        from backend.app.services.extraction import _call_gpt4o_vision

        error = _make_openai_status_error(openai.RateLimitError, status_code=429)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=error)

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
            patch(
                "backend.app.services.extraction._call_gpt4o_vision.retry.wait",
                return_value=0,
            ),
        ):
            with pytest.raises(openai.RateLimitError):
                await _call_gpt4o_vision("https://example.com/rx.jpg")

        assert mock_client.chat.completions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_logs_before_sleep(self):
        """Test 18: Retry attempt is logged before sleep."""
        from backend.app.services.extraction import _call_gpt4o_vision

        error = _make_openai_status_error(openai.RateLimitError, status_code=429)
        mock_response = _make_mock_openai_response('{"doc_type": "prescription"}')

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=[error, mock_response])

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
            patch(
                "backend.app.services.extraction._call_gpt4o_vision.retry.wait",
                return_value=0,
            ),
            patch("backend.app.services.extraction.logger") as mock_logger,
        ):
            await _call_gpt4o_vision("https://example.com/rx.jpg")

        # Check that a warning log was emitted about the retry
        warning_calls = mock_logger.warning.call_args_list
        assert len(warning_calls) >= 1
        retry_log = str(warning_calls[0])
        assert "retry" in retry_log.lower() or "attempt" in retry_log.lower()


# ===========================================================================
# Tests 19–20: Image download error wrapping
# ===========================================================================


class TestImageDownloadErrorWrapping:
    """Tests 19–20: httpx errors become ImageNotReadableError."""

    @pytest.mark.asyncio
    async def test_download_http_error_becomes_image_not_readable(self):
        """Test 19: httpx.HTTPStatusError becomes ImageNotReadableError."""
        from backend.app.services.extraction import (
            ImageNotReadableError,
            extract_prescription,
        )

        mock_request = httpx.Request("GET", IMAGE_URL)
        mock_response = httpx.Response(404, request=mock_request)
        http_error = httpx.HTTPStatusError(
            "Not Found", request=mock_request, response=mock_response
        )

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            side_effect=http_error,
        ):
            with pytest.raises(ImageNotReadableError) as exc_info:
                await extract_prescription(IMAGE_URL)

        # Original exception is chained
        assert exc_info.value.__cause__ is http_error

    @pytest.mark.asyncio
    async def test_download_timeout_becomes_image_not_readable(self):
        """Test 20: httpx.TimeoutException becomes ImageNotReadableError."""
        from backend.app.services.extraction import (
            ImageNotReadableError,
            extract_prescription,
        )

        timeout_error = httpx.TimeoutException("Connection timed out")

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            side_effect=timeout_error,
        ):
            with pytest.raises(ImageNotReadableError) as exc_info:
                await extract_prescription(IMAGE_URL)

        # Original exception is chained
        assert exc_info.value.__cause__ is timeout_error
