"""Tests for app/models/schemas.py

Covers:
    - Enum membership and string values
    - TwilioWebhookPayload alias parsing and defaults
    - Medication and PrescriptionData field defaults
    - UserSession default state and JSON round-trip
    - TranslationLogCreate required fields and defaults
    - TranslationLogRead ORM mode
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from app.models.schemas import (
    ConversationState,
    DocumentType,
    Medication,
    PrescriptionData,
    TranslationLogCreate,
    TranslationLogRead,
    TwilioWebhookPayload,
    UserSession,
)


# ── ConversationState ──────────────────────────────────────────────────────────

def test_conversation_state_values():
    assert ConversationState.WAITING_FOR_IMAGE    == "waiting_for_image"
    assert ConversationState.WAITING_FOR_LANGUAGE == "waiting_for_language"
    assert ConversationState.DONE                 == "done"
    assert ConversationState.ERROR                == "error"


def test_conversation_state_is_str():
    """Enum inherits from str — usable directly as a string."""
    assert isinstance(ConversationState.PROCESSING, str)


# ── DocumentType ───────────────────────────────────────────────────────────────

def test_document_type_values():
    assert DocumentType.PRESCRIPTION      == "prescription"
    assert DocumentType.LAB_REPORT        == "lab_report"
    assert DocumentType.DISCHARGE_SUMMARY == "discharge_summary"
    assert DocumentType.UNKNOWN           == "unknown"


# ── TwilioWebhookPayload ───────────────────────────────────────────────────────

def test_twilio_payload_parses_aliases():
    """Twilio sends capitalised field names; model must accept them."""
    payload = TwilioWebhookPayload(
        **{
            "From": "whatsapp:+919876543210",
            "To": "whatsapp:+14155238886",
            "Body": "Hello",
            "NumMedia": "0",
            "MessageSid": "SMxxx",
        }
    )
    assert payload.From == "whatsapp:+919876543210"
    assert payload.Body == "Hello"
    assert payload.NumMedia == 0


def test_twilio_payload_defaults():
    payload = TwilioWebhookPayload(
        **{"From": "whatsapp:+91", "To": "whatsapp:+1", "MessageSid": "SM1"}
    )
    assert payload.Body == ""
    assert payload.NumMedia == 0
    assert payload.MediaUrl0 is None
    assert payload.MediaContentType0 is None


def test_twilio_payload_ignores_extra_fields():
    """Extra Twilio fields (AccountSid, etc.) must not raise."""
    payload = TwilioWebhookPayload(
        **{
            "From": "whatsapp:+91",
            "To": "whatsapp:+1",
            "MessageSid": "SM1",
            "AccountSid": "AC123",   # extra — should be ignored
            "SmsStatus": "received", # extra
        }
    )
    assert payload.MessageSid == "SM1"


def test_twilio_payload_missing_required_raises():
    with pytest.raises(ValidationError):
        TwilioWebhookPayload(**{"From": "whatsapp:+91", "To": "whatsapp:+1"})
        # MessageSid missing


# ── Medication ─────────────────────────────────────────────────────────────────

def test_medication_required_name():
    with pytest.raises(ValidationError):
        Medication()  # name is required


def test_medication_defaults():
    med = Medication(name="Paracetamol")
    assert med.dosage       == ""
    assert med.frequency    == ""
    assert med.duration     == ""
    assert med.quantity     == ""
    assert med.instructions == ""


def test_medication_full():
    med = Medication(
        name="Amoxicillin",
        dosage="500mg",
        frequency="three times daily",
        duration="7 days",
        quantity="21 capsules",
        instructions="take with food",
    )
    assert med.name      == "Amoxicillin"
    assert med.frequency == "three times daily"


# ── PrescriptionData ───────────────────────────────────────────────────────────

def test_prescription_defaults():
    rx = PrescriptionData()
    assert rx.doc_type    == DocumentType.UNKNOWN
    assert rx.medications == []
    assert rx.diagnosis   == ""
    assert rx.warnings    == []
    assert rx.raw_text    == ""


def test_prescription_with_medications():
    rx = PrescriptionData(
        doc_type=DocumentType.PRESCRIPTION,
        medications=[Medication(name="Metformin", dosage="500mg")],
        diagnosis="Type 2 Diabetes",
    )
    assert rx.doc_type == DocumentType.PRESCRIPTION
    assert len(rx.medications) == 1
    assert rx.medications[0].name == "Metformin"


# ── UserSession ────────────────────────────────────────────────────────────────

def test_user_session_defaults():
    session = UserSession()
    assert session.state         == ConversationState.WAITING_FOR_IMAGE
    assert session.language_code is None
    assert session.prescription  is None
    assert isinstance(session.created_at, datetime)


def test_user_session_json_round_trip():
    """Session must survive serialisation to JSON and back (Redis storage)."""
    session = UserSession(
        state=ConversationState.WAITING_FOR_LANGUAGE,
        language_code="hi",
        language_name="Hindi",
    )
    json_str = session.model_dump_json()
    restored = UserSession.model_validate_json(json_str)
    assert restored.state         == ConversationState.WAITING_FOR_LANGUAGE
    assert restored.language_code == "hi"


def test_user_session_with_prescription():
    rx = PrescriptionData(medications=[Medication(name="Aspirin")])
    session = UserSession(prescription=rx)
    assert session.prescription.medications[0].name == "Aspirin"

    # round-trip with nested prescription
    restored = UserSession.model_validate_json(session.model_dump_json())
    assert restored.prescription.medications[0].name == "Aspirin"


# ── TranslationLogCreate ───────────────────────────────────────────────────────

def test_translation_log_create_required():
    with pytest.raises(ValidationError):
        TranslationLogCreate()  # all required fields missing


def test_translation_log_create_defaults():
    log = TranslationLogCreate(
        request_id="SMxxx",
        phone_hash="a" * 64,
        language_code="hi",
        doc_type="prescription",
        latency_ms=1200,
    )
    assert log.drug_count  == 0
    assert log.has_audio   is False
    assert log.status      == "success"
    assert log.error_code  is None


# ── TranslationLogRead ─────────────────────────────────────────────────────────

def test_translation_log_read_from_orm():
    """from_attributes=True lets us build from an ORM object (or a mock)."""
    class FakeRow:
        id            = 1
        request_id    = "SMxxx"
        phone_hash    = "a" * 64
        language_code = "hi"
        doc_type      = "prescription"
        latency_ms    = 800
        drug_count    = 2
        has_audio     = True
        status        = "success"
        error_code    = None
        created_at    = datetime(2026, 2, 26, 12, 0, 0)

    log = TranslationLogRead.model_validate(FakeRow())
    assert log.id         == 1
    assert log.drug_count == 2
    assert log.has_audio  is True