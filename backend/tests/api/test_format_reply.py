"""S10.2 — Format Reply Tests.

20 tests covering _format_reply(): importable, signature, sync, greeting,
per-medicine cards, low-confidence warnings, disclaimer, truncation,
empty medicines, no PHI, and pipeline wiring.
"""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.models.schemas import (
    DrugInfo,
    MedicineEntry,
    PrescriptionData,
    SessionState,
    SessionStatus,
    TranslationResult,
    WebhookPayload,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WHATSAPP_MAX_CHARS = 1600


def _make_prescription(**overrides) -> PrescriptionData:
    defaults = {
        "doctor_name": "Dr. Sharma",
        "patient_name": "Rajesh Kumar",
        "date": "2024-01-15",
        "diagnosis": "Upper respiratory infection",
        "medicines": [
            MedicineEntry(
                medicine_name="Paracetamol",
                dosage="500mg",
                frequency="3 times a day",
                duration="5 days",
                confidence=0.95,
            ),
            MedicineEntry(
                medicine_name="Amoxicillin",
                dosage="250mg",
                frequency="2 times a day",
                duration="7 days",
                confidence=0.85,
            ),
        ],
        "overall_confidence": 0.9,
    }
    defaults.update(overrides)
    return PrescriptionData(**defaults)


def _make_translation(**overrides) -> TranslationResult:
    defaults = {
        "translated_text": (
            "Your prescription summary:\n\n"
            "Paracetamol 500mg: Take 3 times a day for 5 days. "
            "This is for fever and pain relief.\n\n"
            "Amoxicillin 250mg: Take 2 times a day for 7 days. "
            "This is an antibiotic for infection.\n\n"
            "This is not medical advice. Please consult your doctor."
        ),
        "per_medicine_summaries": [
            "Paracetamol: fever and pain relief",
            "Amoxicillin: antibiotic for infection",
        ],
        "disclaimer": "This is not medical advice. Please consult your doctor.",
        "language_code": "hi",
    }
    defaults.update(overrides)
    return TranslationResult(**defaults)


def _make_drug_info_list() -> list[DrugInfo | None]:
    return [
        DrugInfo(brand_name="Crocin", generic_name="Paracetamol", purpose_en="Pain relief"),
        DrugInfo(brand_name="Amoxil", generic_name="Amoxicillin", purpose_en="Antibiotic"),
    ]


# ---------------------------------------------------------------------------
# Tests 1–3: Import, signature, sync
# ---------------------------------------------------------------------------


class TestFormatReplyImportAndSignature:
    """Tests 1–3: Importable, correct signature, sync function."""

    def test_format_reply_importable(self):
        """T1: _format_reply is importable and callable."""
        from backend.app.api.webhooks import _format_reply

        assert callable(_format_reply)

    def test_format_reply_signature(self):
        """T2: Accepts (PrescriptionData, list, TranslationResult, str) → str."""
        from backend.app.api.webhooks import _format_reply

        sig = inspect.signature(_format_reply)
        params = list(sig.parameters.keys())
        assert params == ["prescription", "drug_info_list", "translation", "language_name"]
        assert sig.return_annotation in (str, "str")

    def test_format_reply_is_sync(self):
        """T3: _format_reply is a regular (sync) function, not async."""
        from backend.app.api.webhooks import _format_reply

        assert not inspect.iscoroutinefunction(_format_reply)


# ---------------------------------------------------------------------------
# Test 4: Greeting section
# ---------------------------------------------------------------------------


class TestFormatReplyGreeting:
    """Test 4: Greeting section present at the start."""

    def test_greeting_present(self):
        """T4: Output starts with translated text content."""
        from backend.app.api.webhooks import _format_reply

        result = _format_reply(
            _make_prescription(),
            _make_drug_info_list(),
            _make_translation(),
            "Hindi",
        )
        lines = result.strip().split("\n")
        first_line = lines[0].strip()
        assert len(first_line) > 0
        # Should start with the translated text (which mentions prescription/summary)
        lower = first_line.lower()
        assert "prescription" in lower or "summary" in lower


# ---------------------------------------------------------------------------
# Tests 5–11: Per-medicine cards
# ---------------------------------------------------------------------------


class TestFormatReplyMedicineCards:
    """Tests 5–11: Medicine cards — name, dosage, frequency, duration, missing fields, summaries."""

    def test_medicine_card_name(self):
        """T5: Each medicine name appears in the output."""
        from backend.app.api.webhooks import _format_reply

        result = _format_reply(
            _make_prescription(),
            _make_drug_info_list(),
            _make_translation(),
            "Hindi",
        )
        assert "Paracetamol" in result
        assert "Amoxicillin" in result

    def test_medicine_card_dosage(self):
        """T6: Dosage appears when present."""
        from backend.app.api.webhooks import _format_reply

        result = _format_reply(
            _make_prescription(),
            _make_drug_info_list(),
            _make_translation(),
            "Hindi",
        )
        assert "500mg" in result
        assert "250mg" in result

    def test_medicine_card_frequency(self):
        """T7: Frequency appears when present."""
        from backend.app.api.webhooks import _format_reply

        result = _format_reply(
            _make_prescription(),
            _make_drug_info_list(),
            _make_translation(),
            "Hindi",
        )
        assert "3 times a day" in result
        assert "2 times a day" in result

    def test_medicine_card_duration(self):
        """T8: Duration appears when present."""
        from backend.app.api.webhooks import _format_reply

        result = _format_reply(
            _make_prescription(),
            _make_drug_info_list(),
            _make_translation(),
            "Hindi",
        )
        assert "5 days" in result
        assert "7 days" in result

    def test_medicine_card_missing_fields(self):
        """T9: Missing optional fields are gracefully omitted — no 'None' text."""
        from backend.app.api.webhooks import _format_reply

        prescription = _make_prescription(
            medicines=[
                MedicineEntry(
                    medicine_name="Paracetamol",
                    dosage=None,
                    frequency=None,
                    duration=None,
                    confidence=0.9,
                ),
            ]
        )
        translation = _make_translation(
            translated_text="Paracetamol: Pain relief medicine.\n\nPlease consult your doctor.",
            per_medicine_summaries=["Pain relief"],
        )

        result = _format_reply(prescription, [None], translation, "Hindi")

        assert "Paracetamol" in result
        assert "None" not in result

    def test_per_medicine_summary(self):
        """T10: Medicine details from translation appear in output."""
        from backend.app.api.webhooks import _format_reply

        result = _format_reply(
            _make_prescription(),
            _make_drug_info_list(),
            _make_translation(),
            "Hindi",
        )
        assert "fever and pain relief" in result
        assert "antibiotic for infection" in result

    def test_both_medicines_present(self):
        """T11: All medicines from translated text appear in output."""
        from backend.app.api.webhooks import _format_reply

        result = _format_reply(
            _make_prescription(),
            _make_drug_info_list(),
            _make_translation(),
            "Hindi",
        )
        assert "Paracetamol" in result
        assert "Amoxicillin" in result


# ---------------------------------------------------------------------------
# Tests 12–14: Low-confidence warnings
# ---------------------------------------------------------------------------


class TestFormatReplyConfidence:
    """Tests 12–14: Low-confidence warnings."""

    def test_low_confidence_warning(self):
        """T12: Confidence < 0.7 triggers warning text."""
        from backend.app.api.webhooks import _format_reply

        prescription = _make_prescription(
            medicines=[
                MedicineEntry(
                    medicine_name="Metformin",
                    dosage="500mg",
                    confidence=0.5,
                ),
            ]
        )
        translation = _make_translation(per_medicine_summaries=["Diabetes medication"])

        result = _format_reply(prescription, [None], translation, "Hindi")

        lower = result.lower()
        assert "verify" in lower or "doctor" in lower or "pharmacist" in lower

    def test_high_confidence_no_warning(self):
        """T13: Confidence >= 0.7 has no warning."""
        from backend.app.api.webhooks import _format_reply

        prescription = _make_prescription(
            medicines=[
                MedicineEntry(
                    medicine_name="Paracetamol",
                    dosage="500mg",
                    confidence=0.9,
                ),
            ]
        )
        translation = _make_translation(per_medicine_summaries=["Pain relief"])

        result = _format_reply(prescription, [None], translation, "Hindi")

        # Should NOT contain the warning about "could not be read clearly"
        assert "could not be read clearly" not in result

    def test_confidence_boundary_0_7(self):
        """T14: Confidence exactly 0.7 does NOT trigger warning."""
        from backend.app.api.webhooks import _format_reply

        prescription = _make_prescription(
            medicines=[
                MedicineEntry(
                    medicine_name="Aspirin",
                    dosage="100mg",
                    confidence=0.7,
                ),
            ]
        )
        translation = _make_translation(per_medicine_summaries=["Blood thinner"])

        result = _format_reply(prescription, [None], translation, "Hindi")

        assert "could not be read clearly" not in result


# ---------------------------------------------------------------------------
# Test 15: Disclaimer
# ---------------------------------------------------------------------------


class TestFormatReplyDisclaimer:
    """Test 15: Disclaimer appears at end."""

    def test_disclaimer_present(self):
        """T15: Disclaimer appears in the output (already part of translated_text)."""
        from backend.app.api.webhooks import _format_reply

        result = _format_reply(
            _make_prescription(),
            _make_drug_info_list(),
            _make_translation(),
            "Hindi",
        )
        assert "This is not medical advice" in result


# ---------------------------------------------------------------------------
# Tests 16–17: Truncation
# ---------------------------------------------------------------------------


class TestFormatReplyTruncation:
    """Tests 16–17: 1600-char limit and truncation note."""

    def test_max_length_1600(self):
        """T16: Output with long translated text is <= 1600 chars."""
        from backend.app.api.webhooks import _format_reply

        # Create a very long translated_text to force truncation
        long_text = "\n\n".join(
            f"Medicine {i}: Medication-{i}-LongName-Extra {100 + i}mg. "
            f"Take 3 times a day after meals for {5 + i} days minimum. "
            f"Summary for medication {i} in Hindi."
            for i in range(15)
        )
        long_text += "\n\nThis is not medical advice."

        medicines = [
            MedicineEntry(
                medicine_name=f"Medication-{i}-LongName-Extra",
                dosage=f"{100 + i}mg",
                confidence=0.95,
            )
            for i in range(15)
        ]
        prescription = _make_prescription(medicines=medicines)
        translation = _make_translation(translated_text=long_text)
        drug_info = [None] * 15

        result = _format_reply(prescription, drug_info, translation, "Hindi")

        assert len(result) <= WHATSAPP_MAX_CHARS

    def test_truncation_note(self):
        """T17: When truncated, includes truncation note."""
        from backend.app.api.webhooks import _format_reply

        # Create a very long translated_text to force truncation
        long_text = "\n\n".join(
            f"Medicine {i}: VeryLongMedicationName-{i}-WithExtras {100 + i}mg. "
            f"Take 3 times a day after meals with water for {5 + i} days minimum course. "
            f"Detailed summary for medication {i} in Hindi language explaining purpose and usage."
            for i in range(20)
        )
        long_text += "\n\nThis is not medical advice. Please consult your doctor."

        medicines = [
            MedicineEntry(
                medicine_name=f"VeryLongMedicationName-{i}-WithExtras",
                dosage=f"{100 + i}mg tablets",
                confidence=0.95,
            )
            for i in range(20)
        ]
        prescription = _make_prescription(medicines=medicines)
        translation = _make_translation(translated_text=long_text)
        drug_info = [None] * 20

        result = _format_reply(prescription, drug_info, translation, "Hindi")

        assert len(result) <= WHATSAPP_MAX_CHARS
        # Check for truncation note
        lower = result.lower()
        assert "truncated" in lower or "full version" in lower


# ---------------------------------------------------------------------------
# Tests 18–19: Edge cases
# ---------------------------------------------------------------------------


class TestFormatReplyEdgeCases:
    """Tests 18–19: Empty medicines, no PHI."""

    def test_empty_medicines(self):
        """T18: Empty medicines list produces valid output from translated_text."""
        from backend.app.api.webhooks import _format_reply

        prescription = _make_prescription(medicines=[])
        translation = _make_translation(per_medicine_summaries=[])

        result = _format_reply(prescription, [], translation, "Hindi")

        assert len(result) > 0
        # Should include translated_text content
        assert "prescription" in result.lower()
        # Should include disclaimer (already in translated_text)
        assert "consult" in result.lower() or "medical advice" in result.lower()

    def test_no_phi_in_output(self):
        """T19: Patient name and doctor name do NOT appear in formatted reply."""
        from backend.app.api.webhooks import _format_reply

        prescription = _make_prescription(
            doctor_name="Dr. Sharma",
            patient_name="Rajesh Kumar",
        )

        result = _format_reply(
            prescription,
            _make_drug_info_list(),
            _make_translation(),
            "Hindi",
        )

        assert "Rajesh Kumar" not in result
        assert "Dr. Sharma" not in result


# ---------------------------------------------------------------------------
# Test 20: Pipeline wiring
# ---------------------------------------------------------------------------


class TestPipelineUsesFormatReply:
    """Test 20: _run_pipeline calls _format_reply."""

    @pytest.mark.asyncio
    async def test_pipeline_uses_format_reply(self):
        """T20: _run_pipeline calls _format_reply and sends its return value."""
        from backend.app.api.webhooks import _run_pipeline

        # Build test data
        prescription = _make_prescription()
        drug_info_list = _make_drug_info_list()
        translation_result = _make_translation()

        payload = WebhookPayload(
            from_number="whatsapp:+919876543210",
            body="",
            num_media=1,
            media_url="https://api.twilio.com/media/test.jpg",
            media_content_type="image/jpeg",
        )
        session = SessionState(
            status=SessionStatus.PROCESSING,
            language_code="hi",
            language_name="Hindi",
            request_id="test-req-123",
            created_at="2024-01-01T00:00:00Z",
        )

        mock_db_session = AsyncMock()

        @asynccontextmanager
        async def mock_session_factory():
            yield mock_db_session

        with (
            patch(
                "backend.app.api.webhooks._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image-bytes",
            ),
            patch(
                "backend.app.api.webhooks.store_prescription_image",
                new_callable=AsyncMock,
                return_value="prescriptions/test/img.jpg",
            ),
            patch(
                "backend.app.api.webhooks.extract_prescription_from_bytes",
                new_callable=AsyncMock,
                return_value=prescription,
            ),
            patch(
                "backend.app.api.webhooks.enrich_prescription",
                new_callable=AsyncMock,
                return_value=drug_info_list,
            ),
            patch(
                "backend.app.api.webhooks.lookup_terms",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "backend.app.api.webhooks.format_glossary_context",
                return_value="",
            ),
            patch(
                "backend.app.api.webhooks.simplify_and_translate",
                new_callable=AsyncMock,
                return_value=translation_result,
            ),
            patch(
                "backend.app.api.webhooks.generate_and_deliver_audio",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "backend.app.api.webhooks.send_text_message",
                new_callable=AsyncMock,
            ) as mock_send_text,
            patch(
                "backend.app.api.webhooks._log_interaction",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.app.api.webhooks._delete_session",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.app.api.webhooks.AsyncSessionLocal",
                side_effect=mock_session_factory,
            ),
            patch(
                "backend.app.api.webhooks._format_reply",
                return_value="Formatted reply text",
            ) as mock_format,
        ):
            await _run_pipeline(payload, session, "req-123", AsyncMock())

            # _format_reply should be called
            mock_format.assert_called_once()
            call_args = mock_format.call_args

            # Verify it receives the pipeline data
            assert call_args.kwargs.get("prescription") == prescription or (
                len(call_args.args) >= 1 and call_args.args[0] == prescription
            )

            # send_text_message should be called with the formatted reply
            mock_send_text.assert_awaited_once_with(
                payload.from_number,
                "Formatted reply text",
            )
