"""S2.4 — Pydantic Models tests.

Pure model validation tests — no external services, no mocking needed.
"""

import pytest
from pydantic import ValidationError

from backend.app.models.schemas import (
    DrugInfo,
    GlossaryEntry,
    MedicineEntry,
    PrescriptionData,
    SessionState,
    SessionStatus,
    TranslationResult,
    WebhookPayload,
)


# ---------------------------------------------------------------------------
# SessionStatus Enum
# ---------------------------------------------------------------------------


class TestSessionStatus:
    def test_session_status_values(self):
        """All three enum values exist."""
        assert SessionStatus.WAITING_FOR_LANGUAGE is not None
        assert SessionStatus.WAITING_FOR_IMAGE is not None
        assert SessionStatus.PROCESSING is not None

    def test_session_status_is_string_enum(self):
        """Enum values are strings (for JSON serialization)."""
        assert isinstance(SessionStatus.WAITING_FOR_LANGUAGE, str)
        assert isinstance(SessionStatus.WAITING_FOR_IMAGE, str)
        assert isinstance(SessionStatus.PROCESSING, str)
        assert SessionStatus.WAITING_FOR_LANGUAGE == "waiting_for_language"
        assert SessionStatus.WAITING_FOR_IMAGE == "waiting_for_image"
        assert SessionStatus.PROCESSING == "processing"


# ---------------------------------------------------------------------------
# MedicineEntry
# ---------------------------------------------------------------------------


class TestMedicineEntry:
    def test_medicine_entry_valid(self):
        """Create with all fields, verify round-trip."""
        entry = MedicineEntry(
            medicine_name="Paracetamol",
            dosage="500mg",
            frequency="twice daily",
            duration="5 days",
            instructions="after food",
            confidence=0.95,
        )
        assert entry.medicine_name == "Paracetamol"
        assert entry.dosage == "500mg"
        assert entry.frequency == "twice daily"
        assert entry.duration == "5 days"
        assert entry.instructions == "after food"
        assert entry.confidence == 0.95

        # round-trip via model_dump / model_validate
        data = entry.model_dump()
        restored = MedicineEntry.model_validate(data)
        assert restored == entry

    def test_medicine_entry_minimal(self):
        """Only required fields; optional fields default to None."""
        entry = MedicineEntry(medicine_name="Amoxicillin", confidence=0.8)
        assert entry.medicine_name == "Amoxicillin"
        assert entry.confidence == 0.8
        assert entry.dosage is None
        assert entry.frequency is None
        assert entry.duration is None
        assert entry.instructions is None

    def test_medicine_entry_confidence_range(self):
        """Reject confidence < 0.0 and > 1.0."""
        with pytest.raises(ValidationError):
            MedicineEntry(medicine_name="X", confidence=-0.1)
        with pytest.raises(ValidationError):
            MedicineEntry(medicine_name="X", confidence=1.01)

        # boundary values are OK
        low = MedicineEntry(medicine_name="X", confidence=0.0)
        high = MedicineEntry(medicine_name="X", confidence=1.0)
        assert low.confidence == 0.0
        assert high.confidence == 1.0

    def test_medicine_entry_empty_name_rejected(self):
        """Reject empty string for medicine_name."""
        with pytest.raises(ValidationError):
            MedicineEntry(medicine_name="", confidence=0.5)


# ---------------------------------------------------------------------------
# PrescriptionData
# ---------------------------------------------------------------------------


class TestPrescriptionData:
    def test_prescription_data_full(self):
        """Create with all fields including medicines list."""
        med = MedicineEntry(medicine_name="Metformin", confidence=0.9, dosage="500mg")
        rx = PrescriptionData(
            doctor_name="Dr. Sharma",
            patient_name="Ravi Kumar",
            date="2025-01-15",
            diagnosis="Type 2 Diabetes",
            medicines=[med],
            overall_confidence=0.9,
            doc_type="prescription",
        )
        assert rx.doctor_name == "Dr. Sharma"
        assert rx.patient_name == "Ravi Kumar"
        assert rx.date == "2025-01-15"
        assert rx.diagnosis == "Type 2 Diabetes"
        assert len(rx.medicines) == 1
        assert rx.medicines[0].medicine_name == "Metformin"
        assert rx.overall_confidence == 0.9
        assert rx.doc_type == "prescription"

        # round-trip
        data = rx.model_dump()
        restored = PrescriptionData.model_validate(data)
        assert restored == rx

    def test_prescription_data_empty_medicines(self):
        """Valid with empty medicines list (lab report edge case)."""
        rx = PrescriptionData(medicines=[], overall_confidence=0.7)
        assert rx.medicines == []
        assert rx.overall_confidence == 0.7

    def test_prescription_data_confidence_range(self):
        """Reject overall_confidence out of [0.0, 1.0]."""
        with pytest.raises(ValidationError):
            PrescriptionData(medicines=[], overall_confidence=-0.1)
        with pytest.raises(ValidationError):
            PrescriptionData(medicines=[], overall_confidence=1.5)

    def test_prescription_data_default_doc_type(self):
        """Default doc_type is 'prescription'."""
        rx = PrescriptionData(medicines=[], overall_confidence=0.8)
        assert rx.doc_type == "prescription"


# ---------------------------------------------------------------------------
# DrugInfo
# ---------------------------------------------------------------------------


class TestDrugInfo:
    def test_drug_info_valid(self):
        """Create with all fields."""
        drug = DrugInfo(
            brand_name="Crocin",
            generic_name="Paracetamol",
            therapeutic_class="Analgesic",
            purpose_en="Pain relief and fever reduction",
            side_effects_en="Nausea, rash",
            timing_instructions="after meals",
            known_interactions="Avoid with alcohol",
        )
        assert drug.brand_name == "Crocin"
        assert drug.generic_name == "Paracetamol"
        assert drug.therapeutic_class == "Analgesic"
        assert drug.purpose_en == "Pain relief and fever reduction"
        assert drug.side_effects_en == "Nausea, rash"
        assert drug.timing_instructions == "after meals"
        assert drug.known_interactions == "Avoid with alcohol"

    def test_drug_info_minimal(self):
        """Only brand_name required, rest optional."""
        drug = DrugInfo(brand_name="Dolo 650")
        assert drug.brand_name == "Dolo 650"
        assert drug.generic_name is None
        assert drug.therapeutic_class is None
        assert drug.purpose_en is None
        assert drug.side_effects_en is None
        assert drug.timing_instructions is None
        assert drug.known_interactions is None

    def test_drug_info_empty_brand_rejected(self):
        """Reject empty brand_name."""
        with pytest.raises(ValidationError):
            DrugInfo(brand_name="")


# ---------------------------------------------------------------------------
# GlossaryEntry
# ---------------------------------------------------------------------------


class TestGlossaryEntry:
    def test_glossary_entry_valid(self):
        """Create with all three fields."""
        entry = GlossaryEntry(
            term="hypertension",
            explanation="High blood pressure",
            vernacular="\u0909\u091a\u094d\u091a \u0930\u0915\u094d\u0924\u091a\u093e\u092a",
        )
        assert entry.term == "hypertension"
        assert entry.explanation == "High blood pressure"
        assert (
            entry.vernacular
            == "\u0909\u091a\u094d\u091a \u0930\u0915\u094d\u0924\u091a\u093e\u092a"
        )

    def test_glossary_entry_empty_fields_rejected(self):
        """Reject empty term, explanation, or vernacular."""
        with pytest.raises(ValidationError):
            GlossaryEntry(term="", explanation="ok", vernacular="ok")
        with pytest.raises(ValidationError):
            GlossaryEntry(term="ok", explanation="", vernacular="ok")
        with pytest.raises(ValidationError):
            GlossaryEntry(term="ok", explanation="ok", vernacular="")


# ---------------------------------------------------------------------------
# TranslationResult
# ---------------------------------------------------------------------------


class TestTranslationResult:
    def test_translation_result_valid(self):
        """Create with all fields."""
        result = TranslationResult(
            translated_text="Translated output text",
            per_medicine_summaries=["Med 1 summary", "Med 2 summary"],
            disclaimer="This is not medical advice.",
            language_code="hi",
        )
        assert result.translated_text == "Translated output text"
        assert len(result.per_medicine_summaries) == 2
        assert result.disclaimer == "This is not medical advice."
        assert result.language_code == "hi"

    def test_translation_result_empty_text_rejected(self):
        """Reject empty translated_text."""
        with pytest.raises(ValidationError):
            TranslationResult(
                translated_text="",
                per_medicine_summaries=[],
                disclaimer="Disclaimer",
                language_code="hi",
            )

    def test_translation_result_empty_disclaimer_rejected(self):
        """Reject empty disclaimer."""
        with pytest.raises(ValidationError):
            TranslationResult(
                translated_text="Some text",
                per_medicine_summaries=[],
                disclaimer="",
                language_code="hi",
            )


# ---------------------------------------------------------------------------
# WebhookPayload
# ---------------------------------------------------------------------------


class TestWebhookPayload:
    def test_webhook_payload_full(self):
        """Create with all fields including media."""
        payload = WebhookPayload(
            from_number="whatsapp:+919876543210",
            body="Hello",
            num_media=1,
            media_url="https://api.twilio.com/image.jpg",
            media_content_type="image/jpeg",
        )
        assert payload.from_number == "whatsapp:+919876543210"
        assert payload.body == "Hello"
        assert payload.num_media == 1
        assert payload.media_url == "https://api.twilio.com/image.jpg"
        assert payload.media_content_type == "image/jpeg"

    def test_webhook_payload_text_only(self):
        """No media (num_media=0, media_url=None)."""
        payload = WebhookPayload(
            from_number="whatsapp:+919876543210",
            body="Hi there",
        )
        assert payload.num_media == 0
        assert payload.media_url is None
        assert payload.media_content_type is None

    def test_webhook_payload_image_only(self):
        """Empty body, num_media=1, media_url set."""
        payload = WebhookPayload(
            from_number="whatsapp:+919876543210",
            body="",
            num_media=1,
            media_url="https://api.twilio.com/img.jpg",
            media_content_type="image/png",
        )
        assert payload.body == ""
        assert payload.num_media == 1
        assert payload.media_url is not None

    def test_webhook_payload_negative_num_media_rejected(self):
        """Reject num_media < 0."""
        with pytest.raises(ValidationError):
            WebhookPayload(
                from_number="whatsapp:+919876543210",
                body="test",
                num_media=-1,
            )

    def test_webhook_payload_empty_from_rejected(self):
        """Reject empty from_number."""
        with pytest.raises(ValidationError):
            WebhookPayload(from_number="", body="test")


# ---------------------------------------------------------------------------
# SessionState
# ---------------------------------------------------------------------------


class TestSessionState:
    def test_session_state_valid(self):
        """Create with all fields."""
        state = SessionState(
            status=SessionStatus.WAITING_FOR_IMAGE,
            language_code="hi",
            language_name="Hindi",
            request_id="abc-123",
            created_at="2025-01-15T10:00:00Z",
        )
        assert state.status == SessionStatus.WAITING_FOR_IMAGE
        assert state.language_code == "hi"
        assert state.language_name == "Hindi"
        assert state.request_id == "abc-123"
        assert state.created_at == "2025-01-15T10:00:00Z"

    def test_session_state_new_session_defaults(self):
        """New session: WAITING_FOR_LANGUAGE, language_code=None."""
        state = SessionState(
            status=SessionStatus.WAITING_FOR_LANGUAGE,
            created_at="2025-01-15T10:00:00Z",
        )
        assert state.status == SessionStatus.WAITING_FOR_LANGUAGE
        assert state.language_code is None
        assert state.language_name is None
        assert state.request_id is None

    def test_session_state_json_round_trip(self):
        """model_dump_json() -> model_validate_json() preserves all fields."""
        state = SessionState(
            status=SessionStatus.PROCESSING,
            language_code="ta",
            language_name="Tamil",
            request_id="req-456",
            created_at="2025-01-15T12:00:00Z",
        )
        json_str = state.model_dump_json()
        restored = SessionState.model_validate_json(json_str)
        assert restored == state
        assert restored.status == SessionStatus.PROCESSING
        assert restored.language_code == "ta"

    def test_session_state_status_enum_serialized(self):
        """JSON output includes string enum value, not enum object."""
        state = SessionState(
            status=SessionStatus.WAITING_FOR_LANGUAGE,
            created_at="2025-01-15T10:00:00Z",
        )
        json_str = state.model_dump_json()
        assert "waiting_for_language" in json_str
