"""S2.4 — Pydantic Models.

Shared data contracts for all SehatSamjho services: extraction, translation,
drug lookup, TTS, and webhook state machine.
"""

import enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SessionStatus(str, enum.Enum):
    """WhatsApp conversation session states."""

    WAITING_FOR_LANGUAGE = "waiting_for_language"
    WAITING_FOR_IMAGE = "waiting_for_image"
    PROCESSING = "processing"


# ---------------------------------------------------------------------------
# Extraction models
# ---------------------------------------------------------------------------


class MedicineEntry(BaseModel):
    """A single medicine extracted from a prescription image."""

    medicine_name: str = Field(..., min_length=1)
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None
    instructions: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)


class PrescriptionData(BaseModel):
    """Full structured output from GPT-4O Vision extraction."""

    doctor_name: str | None = None
    patient_name: str | None = None
    date: str | None = None
    diagnosis: str | None = None
    medicines: list[MedicineEntry] = []
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    doc_type: str = "prescription"


# ---------------------------------------------------------------------------
# Drug lookup models
# ---------------------------------------------------------------------------


class DrugInfo(BaseModel):
    """Enrichment data for a medicine from the drug lookup service."""

    brand_name: str = Field(..., min_length=1)
    generic_name: str | None = None
    therapeutic_class: str | None = None
    purpose_en: str | None = None
    side_effects_en: str | None = None
    timing_instructions: str | None = None
    known_interactions: str | None = None


# ---------------------------------------------------------------------------
# Glossary models
# ---------------------------------------------------------------------------


class GlossaryEntry(BaseModel):
    """A medical term with plain-language explanation and vernacular translation."""

    term: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1)
    vernacular: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Translation models
# ---------------------------------------------------------------------------


class TranslationResult(BaseModel):
    """Output from Claude Sonnet 4.6 translation service."""

    translated_text: str = Field(..., min_length=1)
    per_medicine_summaries: list[str] = []
    disclaimer: str = Field(..., min_length=1)
    language_code: str


# ---------------------------------------------------------------------------
# Webhook models
# ---------------------------------------------------------------------------


class WebhookPayload(BaseModel):
    """Parsed incoming Twilio WhatsApp webhook form data."""

    from_number: str = Field(..., min_length=1)
    body: str = ""
    num_media: int = Field(default=0, ge=0)
    media_url: str | None = None
    media_content_type: str | None = None


# ---------------------------------------------------------------------------
# Session models
# ---------------------------------------------------------------------------


class SessionState(BaseModel):
    """WhatsApp conversation session stored in Redis."""

    status: SessionStatus
    language_code: str | None = None
    language_name: str | None = None
    request_id: str | None = None
    created_at: str


# ---------------------------------------------------------------------------
# Web API models
# ---------------------------------------------------------------------------


class WebMedicineDetail(BaseModel):
    """A single medicine with extraction + drug lookup data for the web response."""

    name: str
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None
    confidence: float | None = None
    purpose: str | None = None
    side_effects: str | None = None


class WebTranslationResponse(BaseModel):
    """Response from POST /api/translate — full pipeline results for the web UI."""

    request_id: str
    language_code: str
    language_name: str
    medicines: list[WebMedicineDetail] = []
    translated_text: str
    per_medicine_summaries: list[str] = []
    disclaimer: str
    audio_url: str | None = None
    latency_ms: int
