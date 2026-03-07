"""S10.3 — Format Audio Text Tests.

20 tests covering _format_audio_text(): importable, signature, sync, strip emoji,
strip markdown, strip bullets, strip special unicode, spoken greeting, medicine names,
dosage in spoken form, missing fields graceful, disclaimer present, disclaimer stripped,
max length 2000, truncation ends sentence, truncation fallback note, empty medicines,
single medicine, no PHI, pipeline wiring.
"""

from __future__ import annotations

import inspect
import re
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.models.schemas import (
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

AUDIO_MAX_CHARS = 2000

# Regex to detect emoji (common Unicode emoji ranges)
EMOJI_PATTERN = re.compile(
    "[\U0001f600-\U0001f64f"  # emoticons
    "\U0001f300-\U0001f5ff"  # symbols & pictographs
    "\U0001f680-\U0001f6ff"  # transport & map
    "\U0001f1e0-\U0001f1ff"  # flags
    "\U00002702-\U000027b0"  # dingbats
    "\U000024c2-\U0001f251"  # enclosed characters
    "\U0000fe0f"  # variation selector
    "\U0000200d"  # zero-width joiner
    "\U00002600-\U000026ff"  # misc symbols
    "\U0000231a-\U0000231b"  # watch/hourglass
    "]"
)


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
            "Your prescription summary.\n\n"
            "Paracetamol 500mg, dosage is 500mg, to be taken 3 times a day, for 5 days. "
            "This is for fever and pain relief.\n\n"
            "Amoxicillin 250mg, dosage is 250mg, to be taken 2 times a day, for 7 days. "
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


# ---------------------------------------------------------------------------
# Tests 1–3: Import, signature, sync
# ---------------------------------------------------------------------------


class TestFormatAudioTextImportAndSignature:
    """Tests 1–3: Importable, correct signature, sync function."""

    def test_format_audio_text_importable(self):
        """T1: _format_audio_text is importable and callable."""
        from backend.app.api.webhooks import _format_audio_text

        assert callable(_format_audio_text)

    def test_format_audio_text_signature(self):
        """T2: Accepts (PrescriptionData, TranslationResult, str) -> str."""
        from backend.app.api.webhooks import _format_audio_text

        sig = inspect.signature(_format_audio_text)
        params = list(sig.parameters.keys())
        assert params == ["prescription", "translation", "language_name"]
        assert sig.return_annotation in (str, "str")

    def test_format_audio_text_sync(self):
        """T3: _format_audio_text is a regular (sync) function, not async."""
        from backend.app.api.webhooks import _format_audio_text

        assert not inspect.iscoroutinefunction(_format_audio_text)


# ---------------------------------------------------------------------------
# Tests 4–7: Stripping emoji, markdown, bullets, special Unicode
# ---------------------------------------------------------------------------


class TestFormatAudioTextStripping:
    """Tests 4–7: Strip emoji, markdown, bullet points, special Unicode."""

    def test_no_emoji_in_output(self):
        """T4: Output contains zero emoji characters."""
        from backend.app.api.webhooks import _format_audio_text

        # Use a translation with emoji in it
        translation = _make_translation(
            translated_text="Take your medicine daily \U0001f48a for good health \u2764\ufe0f",
            disclaimer="\u26a0\ufe0f This is not medical advice \U0001f3e5",
        )

        result = _format_audio_text(_make_prescription(), translation, "Hindi")

        assert not EMOJI_PATTERN.search(result), f"Found emoji in output: {result}"

    def test_no_markdown_in_output(self):
        """T5: Output contains no markdown formatting (*, **, #, backticks)."""
        from backend.app.api.webhooks import _format_audio_text

        translation = _make_translation(
            translated_text="**Bold** and *italic* and `code` and # Heading",
            per_medicine_summaries=[
                "**Paracetamol**: _fever_ and pain relief",
                "## Amoxicillin: antibiotic",
            ],
        )

        result = _format_audio_text(_make_prescription(), translation, "Hindi")

        # No markdown characters used as formatting
        # (stars at line start or around words, backticks, heading hashes)
        assert "**" not in result
        assert "`" not in result
        # Standalone # at line start (heading marker)
        for line in result.split("\n"):
            stripped = line.strip()
            assert not stripped.startswith("#"), f"Markdown heading found: {stripped}"

    def test_no_bullet_points(self):
        """T6: Output contains no bullet-point characters."""
        from backend.app.api.webhooks import _format_audio_text

        result = _format_audio_text(_make_prescription(), _make_translation(), "Hindi")

        assert "\u2022" not in result  # bullet character

    def test_no_special_unicode(self):
        """T7: Output has no warning symbols or decorative em-dashes."""
        from backend.app.api.webhooks import _format_audio_text

        translation = _make_translation(
            disclaimer="\u26a0\ufe0f Warning \u2014 not medical advice",
        )

        result = _format_audio_text(_make_prescription(), translation, "Hindi")

        assert "\u26a0" not in result  # warning symbol


# ---------------------------------------------------------------------------
# Test 8: Spoken greeting
# ---------------------------------------------------------------------------


class TestFormatAudioTextGreeting:
    """Test 8: Spoken greeting present."""

    def test_spoken_greeting(self):
        """T8: Output starts with content mentioning prescription/summary."""
        from backend.app.api.webhooks import _format_audio_text

        result = _format_audio_text(_make_prescription(), _make_translation(), "Hindi")

        # First part should mention "prescription" or "summary"
        first_part = result[:200].lower()
        assert "prescription" in first_part or "summary" in first_part


# ---------------------------------------------------------------------------
# Tests 9–11: Medicine names, dosage, missing fields
# ---------------------------------------------------------------------------


class TestFormatAudioTextMedicines:
    """Tests 9–11: Medicine names, dosage spoken form, missing fields graceful."""

    def test_medicine_name_present(self):
        """T9: Each medicine name appears in the output."""
        from backend.app.api.webhooks import _format_audio_text

        result = _format_audio_text(_make_prescription(), _make_translation(), "Hindi")

        assert "Paracetamol" in result
        assert "Amoxicillin" in result

    def test_dosage_in_spoken_form(self):
        """T10: Dosage appears in a natural spoken form."""
        from backend.app.api.webhooks import _format_audio_text

        result = _format_audio_text(_make_prescription(), _make_translation(), "Hindi")

        assert "500mg" in result

    def test_missing_fields_graceful(self):
        """T11: Missing optional fields don't produce 'None' in output."""
        from backend.app.api.webhooks import _format_audio_text

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

        result = _format_audio_text(prescription, translation, "Hindi")

        assert "Paracetamol" in result
        assert "None" not in result


# ---------------------------------------------------------------------------
# Tests 12–13: Disclaimer
# ---------------------------------------------------------------------------


class TestFormatAudioTextDisclaimer:
    """Tests 12–13: Disclaimer present and cleaned."""

    def test_disclaimer_present(self):
        """T12: Disclaimer text (cleaned) is present in output."""
        from backend.app.api.webhooks import _format_audio_text

        result = _format_audio_text(_make_prescription(), _make_translation(), "Hindi")

        # Disclaimer content should be there (possibly reformatted)
        lower = result.lower()
        assert "not medical advice" in lower or "consult your doctor" in lower

    def test_disclaimer_stripped(self):
        """T13: Disclaimer with emoji/formatting is stripped clean."""
        from backend.app.api.webhooks import _format_audio_text

        translation = _make_translation(
            disclaimer="\u26a0\ufe0f **Important**: This is _not_ medical advice! \U0001f6d1",
        )

        result = _format_audio_text(_make_prescription(), translation, "Hindi")

        # Disclaimer should be present but cleaned
        assert "not" in result.lower() and "medical advice" in result.lower()
        # No emoji
        assert not EMOJI_PATTERN.search(result)
        # No markdown
        assert "**" not in result


# ---------------------------------------------------------------------------
# Tests 14–16: Length limit and truncation
# ---------------------------------------------------------------------------


class TestFormatAudioTextLength:
    """Tests 14–16: 2000-char limit and truncation."""

    def test_max_length_2000(self):
        """T14: Output with many medicines is <= 2000 chars."""
        from backend.app.api.webhooks import _format_audio_text

        # Create 20 medicines with long names
        medicines = [
            MedicineEntry(
                medicine_name=f"Medication-{i}-VeryLongName-ExtraText",
                dosage=f"{100 + i}mg",
                frequency="3 times a day after meals",
                duration=f"{5 + i} days minimum treatment course",
                confidence=0.95,
            )
            for i in range(20)
        ]
        prescription = _make_prescription(medicines=medicines)
        summaries = [
            f"This is a detailed summary for medication number {i} explaining its purpose"
            for i in range(20)
        ]
        translation = _make_translation(per_medicine_summaries=summaries)

        result = _format_audio_text(prescription, translation, "Hindi")

        assert len(result) <= AUDIO_MAX_CHARS

    def test_truncation_ends_sentence(self):
        """T15: When truncated, ends at a sentence boundary."""
        from backend.app.api.webhooks import _format_audio_text

        # Create enough content to force truncation
        medicines = [
            MedicineEntry(
                medicine_name=f"MedLongNameNumber{i}WithExtraWordsHere",
                dosage=f"{100 + i}mg tablets extended release formulation",
                frequency="three times daily after heavy meals with water",
                duration=f"{5 + i} days minimum mandatory treatment course required",
                confidence=0.95,
            )
            for i in range(25)
        ]
        prescription = _make_prescription(medicines=medicines)
        summaries = [
            f"Detailed summary of medication {i} for Hindi language patients" for i in range(25)
        ]
        translation = _make_translation(per_medicine_summaries=summaries)

        result = _format_audio_text(prescription, translation, "Hindi")

        assert len(result) <= AUDIO_MAX_CHARS
        # Should end with a period or the fallback note
        stripped = result.rstrip()
        assert stripped.endswith(".") or "text message" in stripped.lower()

    def test_truncation_fallback_note(self):
        """T16: When truncated, includes 'read the text message' note."""
        from backend.app.api.webhooks import _format_audio_text

        # Create a very long translated_text to force truncation past 2000 chars
        long_text = " ".join(
            f"ExtendedMedicationName{i}WithVerboseDescription {100 + i}mg extended release coated tablets, "
            f"take three times daily after heavy meals with plenty of water for {5 + i} days minimum "
            f"mandatory treatment course as prescribed. Very detailed summary of medication number {i} "
            f"in Hindi for the patient explaining purpose and usage guidelines."
            for i in range(30)
        )
        long_text += " This is not medical advice. Please consult your doctor."

        medicines = [
            MedicineEntry(
                medicine_name=f"ExtendedMedicationName{i}WithVerboseDescription",
                dosage=f"{100 + i}mg",
                confidence=0.95,
            )
            for i in range(30)
        ]
        prescription = _make_prescription(medicines=medicines)
        translation = _make_translation(translated_text=long_text)

        result = _format_audio_text(prescription, translation, "Hindi")

        assert len(result) <= AUDIO_MAX_CHARS
        lower = result.lower()
        assert "text message" in lower or "read" in lower


# ---------------------------------------------------------------------------
# Tests 17–18: Edge cases
# ---------------------------------------------------------------------------


class TestFormatAudioTextEdgeCases:
    """Tests 17–18: Empty medicines, single medicine."""

    def test_empty_medicines(self):
        """T17: Empty medicines list produces valid spoken output from translated_text."""
        from backend.app.api.webhooks import _format_audio_text

        prescription = _make_prescription(medicines=[])
        translation = _make_translation(per_medicine_summaries=[])

        result = _format_audio_text(prescription, translation, "Hindi")

        assert len(result) > 0
        # Should contain translated text content
        lower = result.lower()
        assert "prescription" in lower or "summary" in lower

    def test_single_medicine(self):
        """T18: Single medicine produces natural speech."""
        from backend.app.api.webhooks import _format_audio_text

        prescription = _make_prescription(
            medicines=[
                MedicineEntry(
                    medicine_name="Paracetamol",
                    dosage="500mg",
                    frequency="3 times a day",
                    duration="5 days",
                    confidence=0.95,
                ),
            ]
        )
        translation = _make_translation(
            translated_text=(
                "Paracetamol 500mg: Take 3 times a day for 5 days for fever and pain relief.\n\n"
                "Please consult your doctor."
            ),
        )

        result = _format_audio_text(prescription, translation, "Hindi")

        assert "Paracetamol" in result


# ---------------------------------------------------------------------------
# Test 19: No PHI
# ---------------------------------------------------------------------------


class TestFormatAudioTextNoPHI:
    """Test 19: No PHI in audio text."""

    def test_no_phi_in_output(self):
        """T19: Patient name and doctor name do NOT appear in audio text."""
        from backend.app.api.webhooks import _format_audio_text

        prescription = _make_prescription(
            doctor_name="Dr. Sharma",
            patient_name="Rajesh Kumar",
        )

        result = _format_audio_text(prescription, _make_translation(), "Hindi")

        assert "Rajesh Kumar" not in result
        assert "Dr. Sharma" not in result


# ---------------------------------------------------------------------------
# Test 20: Pipeline wiring
# ---------------------------------------------------------------------------


class TestPipelineUsesFormatAudioText:
    """Test 20: _run_pipeline calls _format_audio_text and uses its output for TTS."""

    @pytest.mark.asyncio
    async def test_pipeline_uses_format_audio_text(self):
        """T20: _run_pipeline passes _format_audio_text output to generate_and_deliver_audio."""
        from backend.app.api.webhooks import _run_pipeline

        prescription = _make_prescription()
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

        audio_url = "https://s3.amazonaws.com/audio/test.ogg"

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
                return_value=[None, None],
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
                return_value=audio_url,
            ) as mock_audio,
            patch(
                "backend.app.api.webhooks.send_text_message",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.app.api.webhooks.send_audio_message_with_fallback",
                new_callable=AsyncMock,
            ) as mock_send_audio,
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
                "backend.app.api.webhooks._format_audio_text",
                return_value="Cleaned spoken text for TTS",
            ) as mock_format_audio,
        ):
            await _run_pipeline(payload, session, "req-123", AsyncMock())

            # _format_audio_text should be called with pipeline data
            mock_format_audio.assert_called_once()
            call_args = mock_format_audio.call_args
            # First arg (or kwarg) is prescription
            assert call_args.kwargs.get("prescription") == prescription or (
                len(call_args.args) >= 1 and call_args.args[0] == prescription
            )

            # generate_and_deliver_audio should receive the formatted audio text
            mock_audio.assert_awaited_once()
            audio_call = mock_audio.call_args
            assert audio_call.kwargs.get("text") == "Cleaned spoken text for TTS"

            # send_audio_message_with_fallback should use formatted text as fallback
            mock_send_audio.assert_awaited_once()
            fallback_call = mock_send_audio.call_args
            assert fallback_call.kwargs.get("fallback_text") == "Cleaned spoken text for TTS"
