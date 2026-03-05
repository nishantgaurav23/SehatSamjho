"""S7.4 — Tests for simplify_and_translate() orchestrator.

20 tests: import/signature (3), happy path (5), response parsing (5),
edge cases (4), logging (3).  All Claude API calls mocked.
"""

from __future__ import annotations

import asyncio
import inspect
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from loguru import logger

from backend.app.models.schemas import (
    DrugInfo,
    MedicineEntry,
    PrescriptionData,
    TranslationResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_RESPONSE_TEXT = (
    "## Your Prescription Summary\n"
    "\n"
    "Dear patient, here is your prescription explained in simple Hindi.\n"
    "\n"
    "### Metformin 500mg\n"
    "This medicine helps control blood sugar levels. "
    "Take 500mg twice a day, after meals.\n"
    "\n"
    "### Amlodipine 5mg\n"
    "This medicine helps lower blood pressure. "
    "Take 5mg once a day, in the morning.\n"
    "\n"
    "**Disclaimer**: This translation is for understanding only. "
    "Please consult your doctor or pharmacist for medical advice."
)

RESPONSE_NO_DISCLAIMER = (
    "## Your Prescription Summary\n\n### Metformin 500mg\nTake 500mg twice a day, after meals.\n"
)

RESPONSE_NO_MEDICINES = (
    "Your prescription has been reviewed.\n"
    "\n"
    "No specific medicines were identified.\n"
    "\n"
    "**Disclaimer**: This translation is for understanding only. "
    "Please consult your doctor or pharmacist for medical advice."
)


@pytest.fixture()
def sample_prescription() -> PrescriptionData:
    return PrescriptionData(
        doctor_name="Dr. Sharma",
        date="2024-01-15",
        diagnosis="Type 2 Diabetes, Hypertension",
        medicines=[
            MedicineEntry(
                medicine_name="Metformin",
                dosage="500mg",
                frequency="Twice daily",
                duration="3 months",
                instructions="After meals",
                confidence=0.95,
            ),
            MedicineEntry(
                medicine_name="Amlodipine",
                dosage="5mg",
                frequency="Once daily",
                duration="Ongoing",
                instructions="Morning",
                confidence=0.88,
            ),
        ],
        overall_confidence=0.91,
    )


@pytest.fixture()
def minimal_prescription() -> PrescriptionData:
    return PrescriptionData(
        medicines=[
            MedicineEntry(medicine_name="Paracetamol", confidence=0.8),
        ],
        overall_confidence=0.8,
    )


@pytest.fixture()
def sample_drug_info() -> list[DrugInfo]:
    return [
        DrugInfo(
            brand_name="Metformin",
            generic_name="Metformin HCl",
            therapeutic_class="Antidiabetic",
            purpose_en="Controls blood sugar",
            side_effects_en="Nausea, diarrhea",
            timing_instructions="After meals",
            known_interactions="Alcohol",
        ),
    ]


def _make_mock_response(text: str) -> MagicMock:
    """Build a mock anthropic.types.Message with a single TextBlock."""
    block = SimpleNamespace(type="text", text=text)
    response = MagicMock()
    response.content = [block]
    response.usage = SimpleNamespace(input_tokens=100, output_tokens=200)
    return response


def _make_empty_response() -> MagicMock:
    """Build a mock anthropic.types.Message with empty content."""
    response = MagicMock()
    response.content = []
    response.usage = SimpleNamespace(input_tokens=100, output_tokens=0)
    return response


@pytest.fixture()
def mock_client():
    """Patch _get_client to return a mock AsyncAnthropic with messages.create."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=_make_mock_response(SAMPLE_RESPONSE_TEXT))
    with patch("backend.app.services.translation._get_client", return_value=client):
        yield client


# ═══════════════════════════════════════════════════════════════════════════
# Import & Signature (3 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestImportAndSignature:
    """FR-1: function exists, is async, correct signature."""

    def test_import_simplify_and_translate(self):
        from backend.app.services.translation import simplify_and_translate

        assert callable(simplify_and_translate)

    def test_is_async(self):
        from backend.app.services.translation import simplify_and_translate

        assert asyncio.iscoroutinefunction(simplify_and_translate)

    def test_signature_params(self):
        from backend.app.services.translation import simplify_and_translate

        sig = inspect.signature(simplify_and_translate)
        params = list(sig.parameters.keys())
        assert "prescription" in params
        assert "language_name" in params
        assert "language_code" in params
        assert "drug_info_list" in params
        assert "glossary_context" in params
        assert "request_id" in params


# ═══════════════════════════════════════════════════════════════════════════
# Happy Path (5 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestHappyPath:
    """FR-2/3: prompt building + Claude API call."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_translation_result(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        result = await simplify_and_translate(
            prescription=sample_prescription,
            language_name="Hindi",
            language_code="hi",
            request_id="req-001",
        )
        assert isinstance(result, TranslationResult)

    @pytest.mark.asyncio
    async def test_calls_messages_create_with_correct_params(
        self, mock_client, sample_prescription
    ):
        from backend.app.services.translation import (
            CLAUDE_MODEL,
            TRANSLATION_MAX_TOKENS,
            TRANSLATION_TEMPERATURE,
            simplify_and_translate,
        )

        await simplify_and_translate(
            prescription=sample_prescription,
            language_name="Hindi",
            language_code="hi",
            request_id="req-002",
        )
        mock_client.messages.create.assert_awaited_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == CLAUDE_MODEL
        assert call_kwargs["max_tokens"] == TRANSLATION_MAX_TOKENS
        assert call_kwargs["temperature"] == TRANSLATION_TEMPERATURE
        assert "system" in call_kwargs
        assert "messages" in call_kwargs
        assert call_kwargs["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_passes_glossary_to_system_prompt(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        glossary = "Term: Hypertension → Hindi: high blood pressure"
        await simplify_and_translate(
            prescription=sample_prescription,
            language_name="Hindi",
            language_code="hi",
            glossary_context=glossary,
            request_id="req-003",
        )
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert glossary in call_kwargs["system"]

    @pytest.mark.asyncio
    async def test_passes_drug_info_to_user_prompt(
        self, mock_client, sample_prescription, sample_drug_info
    ):
        from backend.app.services.translation import simplify_and_translate

        await simplify_and_translate(
            prescription=sample_prescription,
            language_name="Hindi",
            language_code="hi",
            drug_info_list=sample_drug_info,
            request_id="req-004",
        )
        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_msg = call_kwargs["messages"][0]["content"]
        assert "Metformin" in user_msg
        assert "Antidiabetic" in user_msg

    @pytest.mark.asyncio
    async def test_language_code_in_result(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        result = await simplify_and_translate(
            prescription=sample_prescription,
            language_name="Tamil",
            language_code="ta",
            request_id="req-005",
        )
        assert result.language_code == "ta"


# ═══════════════════════════════════════════════════════════════════════════
# Response Parsing (5 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestResponseParsing:
    """FR-4/5: parse Claude response into TranslationResult."""

    @pytest.mark.asyncio
    async def test_extracts_translated_text(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        result = await simplify_and_translate(
            prescription=sample_prescription,
            language_name="Hindi",
            language_code="hi",
            request_id="req-006",
        )
        assert len(result.translated_text) > 0
        assert "prescription" in result.translated_text.lower() or len(result.translated_text) > 10

    @pytest.mark.asyncio
    async def test_extracts_disclaimer_from_response(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        result = await simplify_and_translate(
            prescription=sample_prescription,
            language_name="Hindi",
            language_code="hi",
            request_id="req-007",
        )
        assert "consult" in result.disclaimer.lower() or "disclaimer" in result.disclaimer.lower()

    @pytest.mark.asyncio
    async def test_default_disclaimer_when_missing(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(return_value=_make_mock_response(RESPONSE_NO_DISCLAIMER))
        with patch("backend.app.services.translation._get_client", return_value=client):
            result = await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-008",
            )
        assert len(result.disclaimer) > 0
        assert "consult" in result.disclaimer.lower()

    @pytest.mark.asyncio
    async def test_extracts_per_medicine_summaries(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        result = await simplify_and_translate(
            prescription=sample_prescription,
            language_name="Hindi",
            language_code="hi",
            request_id="req-009",
        )
        assert isinstance(result.per_medicine_summaries, list)
        assert len(result.per_medicine_summaries) >= 1

    @pytest.mark.asyncio
    async def test_empty_medicines_yields_empty_summaries(self):
        from backend.app.services.translation import simplify_and_translate

        rx = PrescriptionData(medicines=[], overall_confidence=0.9)
        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(return_value=_make_mock_response(RESPONSE_NO_MEDICINES))
        with patch("backend.app.services.translation._get_client", return_value=client):
            result = await simplify_and_translate(
                prescription=rx,
                language_name="Hindi",
                language_code="hi",
                request_id="req-010",
            )
        assert isinstance(result.per_medicine_summaries, list)


# ═══════════════════════════════════════════════════════════════════════════
# Edge Cases (4 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """FR-4: empty/malformed responses, optional params."""

    @pytest.mark.asyncio
    async def test_empty_response_content(self, sample_prescription):
        from backend.app.services.translation import TranslationError, simplify_and_translate

        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(return_value=_make_empty_response())
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            pytest.raises(TranslationError, match="[Ee]mpty"),
        ):
            await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-011",
            )

    @pytest.mark.asyncio
    async def test_no_drug_info(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        result = await simplify_and_translate(
            prescription=sample_prescription,
            language_name="Hindi",
            language_code="hi",
            drug_info_list=None,
            request_id="req-012",
        )
        assert isinstance(result, TranslationResult)

    @pytest.mark.asyncio
    async def test_no_glossary_context(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        result = await simplify_and_translate(
            prescription=sample_prescription,
            language_name="Hindi",
            language_code="hi",
            glossary_context="",
            request_id="req-013",
        )
        assert isinstance(result, TranslationResult)

    @pytest.mark.asyncio
    async def test_minimal_prescription(self, mock_client, minimal_prescription):
        from backend.app.services.translation import simplify_and_translate

        result = await simplify_and_translate(
            prescription=minimal_prescription,
            language_name="Hindi",
            language_code="hi",
            request_id="req-014",
        )
        assert isinstance(result, TranslationResult)
        assert result.language_code == "hi"


# ═══════════════════════════════════════════════════════════════════════════
# Logging (3 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestLogging:
    """FR-6/7: PHI-safe logging with request_id."""

    @pytest.mark.asyncio
    async def test_logs_success_with_request_id(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="DEBUG")
        try:
            await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-log-001",
            )
            log_output = sink.getvalue()
            assert "req-log-001" in log_output
        finally:
            logger.remove(handler_id)

    @pytest.mark.asyncio
    async def test_logs_response_length(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="DEBUG")
        try:
            await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-log-002",
            )
            log_output = sink.getvalue()
            # Should log response length (chars or tokens)
            assert "len" in log_output.lower() or str(len(SAMPLE_RESPONSE_TEXT)) in log_output
        finally:
            logger.remove(handler_id)

    @pytest.mark.asyncio
    async def test_never_logs_translated_text(self, mock_client, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="DEBUG")
        try:
            await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-log-003",
            )
            log_output = sink.getvalue()
            # The actual translated content must not appear in logs
            assert "Dear patient, here is your prescription" not in log_output
            assert "helps control blood sugar" not in log_output
        finally:
            logger.remove(handler_id)
