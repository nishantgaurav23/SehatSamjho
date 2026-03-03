"""S5.4 — Tests for extract_prescription() public orchestration function.

20 tests covering: import/signature, happy path, URL validation,
JSON parsing (invalid, empty, code fences), Pydantic validation,
logging (start, completion, error, no PHI), call forwarding, error propagation.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

VALID_JSON = json.dumps(
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
            {
                "medicine_name": "Metformin",
                "dosage": "500mg",
                "frequency": "Twice daily",
                "duration": None,
                "instructions": None,
                "confidence": 0.7,
            },
        ],
        "overall_confidence": 0.85,
        "doc_type": "prescription",
    }
)

IMAGE_URL = "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages/MM456/Media/ME789"


# ===================================================================
# Tests 1–3: Import, async, signature
# ===================================================================


class TestExtractPrescriptionImport:
    """Tests 1–3: importability, async nature, signature."""

    def test_extract_prescription_importable(self):
        """Test 1: extract_prescription is importable from the extraction module."""
        from backend.app.services.extraction import extract_prescription

        assert extract_prescription is not None

    def test_extract_prescription_is_async(self):
        """Test 2: extract_prescription is a coroutine function."""
        from backend.app.services.extraction import extract_prescription

        assert asyncio.iscoroutinefunction(extract_prescription)

    def test_extract_prescription_signature(self):
        """Test 3: Accepts image_url (str) and content_type (str, default 'image/jpeg')."""
        from backend.app.services.extraction import extract_prescription

        sig = inspect.signature(extract_prescription)
        params = list(sig.parameters.keys())
        assert "image_url" in params
        assert "content_type" in params
        assert sig.parameters["content_type"].default == "image/jpeg"


# ===================================================================
# Tests 4–6: Happy path
# ===================================================================


class TestExtractPrescriptionHappyPath:
    """Tests 4–6: happy path, medicines detail, content_type forwarding."""

    @pytest.mark.asyncio
    async def test_extract_prescription_happy_path(self):
        """Test 4: Returns PrescriptionData with correct top-level fields."""
        from backend.app.models.schemas import PrescriptionData
        from backend.app.services.extraction import extract_prescription

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=VALID_JSON,
        ):
            result = await extract_prescription(IMAGE_URL)

        assert isinstance(result, PrescriptionData)
        assert result.doctor_name == "Dr. Sharma"
        assert result.overall_confidence == 0.85
        assert result.doc_type == "prescription"

    @pytest.mark.asyncio
    async def test_extract_prescription_happy_path_medicines(self):
        """Test 5: Returned PrescriptionData.medicines has correct count and fields."""
        from backend.app.services.extraction import extract_prescription

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=VALID_JSON,
        ):
            result = await extract_prescription(IMAGE_URL)

        assert len(result.medicines) == 2
        assert result.medicines[0].medicine_name == "Amlodipine"
        assert result.medicines[0].dosage == "5mg"
        assert result.medicines[1].medicine_name == "Metformin"
        assert result.medicines[1].confidence == 0.7

    @pytest.mark.asyncio
    async def test_extract_prescription_passes_content_type(self):
        """Test 6: content_type param is forwarded to _call_gpt4o_vision."""
        from backend.app.services.extraction import extract_prescription

        mock_vision = AsyncMock(return_value=VALID_JSON)
        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            mock_vision,
        ):
            await extract_prescription(IMAGE_URL, content_type="image/png")

        mock_vision.assert_called_once_with(IMAGE_URL, "image/png")


# ===================================================================
# Tests 7–8: URL validation
# ===================================================================


class TestExtractPrescriptionURLValidation:
    """Tests 7–8: empty and whitespace URL raise ValueError."""

    @pytest.mark.asyncio
    async def test_extract_prescription_empty_url_raises(self):
        """Test 7: Empty string URL raises ValueError."""
        from backend.app.services.extraction import extract_prescription

        with pytest.raises(ValueError, match="[Ii]mage.?[Uu][Rr][Ll]"):
            await extract_prescription("")

    @pytest.mark.asyncio
    async def test_extract_prescription_whitespace_url_raises(self):
        """Test 8: Whitespace-only URL raises ValueError."""
        from backend.app.services.extraction import extract_prescription

        with pytest.raises(ValueError, match="[Ii]mage.?[Uu][Rr][Ll]"):
            await extract_prescription("   ")


# ===================================================================
# Tests 9–10: Invalid JSON / empty response
# ===================================================================


class TestExtractPrescriptionJSONParsing:
    """Tests 9–10: invalid JSON and empty response."""

    @pytest.mark.asyncio
    async def test_extract_prescription_invalid_json_raises(self):
        """Test 9: GPT-4O returning 'not json' raises ValueError."""
        from backend.app.services.extraction import extract_prescription

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value="not json at all",
        ):
            with pytest.raises(ValueError):
                await extract_prescription(IMAGE_URL)

    @pytest.mark.asyncio
    async def test_extract_prescription_empty_response_raises(self):
        """Test 10: GPT-4O returning empty string raises ValueError."""
        from backend.app.services.extraction import extract_prescription

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value="",
        ):
            with pytest.raises(ValueError):
                await extract_prescription(IMAGE_URL)


# ===================================================================
# Tests 11–12: Code fence stripping
# ===================================================================


class TestExtractPrescriptionCodeFences:
    """Tests 11–12: strip markdown code fences."""

    @pytest.mark.asyncio
    async def test_extract_prescription_strips_code_fences(self):
        """Test 11: JSON wrapped in ```json ... ``` is parsed correctly."""
        from backend.app.models.schemas import PrescriptionData
        from backend.app.services.extraction import extract_prescription

        fenced = f"```json\n{VALID_JSON}\n```"
        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=fenced,
        ):
            result = await extract_prescription(IMAGE_URL)

        assert isinstance(result, PrescriptionData)
        assert result.doctor_name == "Dr. Sharma"

    @pytest.mark.asyncio
    async def test_extract_prescription_strips_code_fences_no_lang(self):
        """Test 12: JSON wrapped in ``` ... ``` (no lang) is parsed correctly."""
        from backend.app.models.schemas import PrescriptionData
        from backend.app.services.extraction import extract_prescription

        fenced = f"```\n{VALID_JSON}\n```"
        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=fenced,
        ):
            result = await extract_prescription(IMAGE_URL)

        assert isinstance(result, PrescriptionData)
        assert result.overall_confidence == 0.85


# ===================================================================
# Tests 13–14: Pydantic validation errors
# ===================================================================


class TestExtractPrescriptionValidation:
    """Tests 13–14: Pydantic validation failures raise ValueError."""

    @pytest.mark.asyncio
    async def test_extract_prescription_validation_error(self):
        """Test 13: confidence: 2.0 (out of range) raises ValueError."""
        from backend.app.services.extraction import extract_prescription

        bad_json = json.dumps(
            {
                "overall_confidence": 0.8,
                "doc_type": "prescription",
                "medicines": [{"medicine_name": "TestDrug", "confidence": 2.0}],
            }
        )
        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=bad_json,
        ):
            with pytest.raises(ValueError):
                await extract_prescription(IMAGE_URL)

    @pytest.mark.asyncio
    async def test_extract_prescription_missing_required_field(self):
        """Test 14: Missing overall_confidence raises ValueError."""
        from backend.app.services.extraction import extract_prescription

        bad_json = json.dumps(
            {
                "doc_type": "prescription",
                "medicines": [],
            }
        )
        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            return_value=bad_json,
        ):
            with pytest.raises(ValueError):
                await extract_prescription(IMAGE_URL)


# ===================================================================
# Tests 15–18: Logging
# ===================================================================


class TestExtractPrescriptionLogging:
    """Tests 15–18: logging start, completion, errors, no PHI."""

    @pytest.mark.asyncio
    async def test_extract_prescription_logs_start(self):
        """Test 15: info logged at extraction start (no image URL in message)."""
        from backend.app.services.extraction import extract_prescription

        with (
            patch(
                "backend.app.services.extraction._call_gpt4o_vision",
                new_callable=AsyncMock,
                return_value=VALID_JSON,
            ),
            patch("backend.app.services.extraction.logger") as mock_logger,
        ):
            await extract_prescription(IMAGE_URL)

        # At least one info call at start
        info_calls = mock_logger.info.call_args_list
        assert len(info_calls) >= 1
        # First info call should NOT contain the image URL
        first_call_str = str(info_calls[0])
        assert IMAGE_URL not in first_call_str

    @pytest.mark.asyncio
    async def test_extract_prescription_logs_completion(self):
        """Test 16: info logged with doc_type and medicine count on success."""
        from backend.app.services.extraction import extract_prescription

        with (
            patch(
                "backend.app.services.extraction._call_gpt4o_vision",
                new_callable=AsyncMock,
                return_value=VALID_JSON,
            ),
            patch("backend.app.services.extraction.logger") as mock_logger,
        ):
            await extract_prescription(IMAGE_URL)

        all_info_args = " ".join(str(c) for c in mock_logger.info.call_args_list)
        assert "prescription" in all_info_args
        assert "2" in all_info_args  # medicine count

    @pytest.mark.asyncio
    async def test_extract_prescription_logs_error_on_invalid_json(self):
        """Test 17: error logged when JSON parsing fails."""
        from backend.app.services.extraction import extract_prescription

        with (
            patch(
                "backend.app.services.extraction._call_gpt4o_vision",
                new_callable=AsyncMock,
                return_value="not json",
            ),
            patch("backend.app.services.extraction.logger") as mock_logger,
        ):
            with pytest.raises(ValueError):
                await extract_prescription(IMAGE_URL)

        assert mock_logger.error.called

    @pytest.mark.asyncio
    async def test_extract_prescription_no_phi_in_logs(self):
        """Test 18: Image URL never appears in any log call arguments."""
        from backend.app.services.extraction import extract_prescription

        with (
            patch(
                "backend.app.services.extraction._call_gpt4o_vision",
                new_callable=AsyncMock,
                return_value=VALID_JSON,
            ),
            patch("backend.app.services.extraction.logger") as mock_logger,
        ):
            await extract_prescription(IMAGE_URL)

        # Check all log method calls (info, debug, error, warning)
        for method_name in ("info", "debug", "error", "warning"):
            method = getattr(mock_logger, method_name)
            for call in method.call_args_list:
                call_str = str(call)
                assert (
                    IMAGE_URL not in call_str
                ), f"Image URL found in logger.{method_name} call: {call_str}"


# ===================================================================
# Tests 19–20: Call verification & error propagation
# ===================================================================


class TestExtractPrescriptionCallBehavior:
    """Tests 19–20: _call_gpt4o_vision called correctly, errors propagate."""

    @pytest.mark.asyncio
    async def test_extract_prescription_calls_gpt4o_vision(self):
        """Test 19: _call_gpt4o_vision called exactly once with correct args."""
        from backend.app.services.extraction import extract_prescription

        mock_vision = AsyncMock(return_value=VALID_JSON)
        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            mock_vision,
        ):
            await extract_prescription(IMAGE_URL)

        mock_vision.assert_called_once_with(IMAGE_URL, "image/jpeg")

    @pytest.mark.asyncio
    async def test_extract_prescription_propagates_gpt4o_errors(self):
        """Test 20: httpx errors from _call_gpt4o_vision wrapped as ImageNotReadableError."""
        from backend.app.services.extraction import (
            ImageNotReadableError,
            extract_prescription,
        )

        mock_request = httpx.Request("GET", IMAGE_URL)
        mock_response = httpx.Response(500, request=mock_request)
        error = httpx.HTTPStatusError("Server Error", request=mock_request, response=mock_response)

        with patch(
            "backend.app.services.extraction._call_gpt4o_vision",
            new_callable=AsyncMock,
            side_effect=error,
        ):
            with pytest.raises(ImageNotReadableError):
                await extract_prescription(IMAGE_URL)
