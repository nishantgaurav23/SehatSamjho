"""
app/models/schemas.py : Pydantic models — everything else depends on these

What it does:
    Defines all Pydantic models used across the app - the data contracts between layers. Nothing imports
    from service files; everything imports from here.

Why first:
    db/models.py, security.py, webhooks.py, all services — they all reference types defined here. It has zero app
    dependencies so it can be validated standalone.

---
Pydantic request/response models for SehatSamjho

This is the single source of truth for data shapes across the stack:
    - TwilioWebhookPayload          : parsed form data from Twilio POST
    - Medication                    : one drug entry extracted from a prescription
    - PrescriptionData              : full GPT-4o Vision output
    - UserSession                   : Redis session state per phone number
    - TranslationLogCreate          : row written to PostgreSQL (zero PHI)
    - TranslationLogRead            : row returned by dashboard API

Integration map:
    TwilioWebhookPayload        ,<- api/webhooks.py         (incoming Twilio POST)
    PrescriptionData             <- services/extraction.py -> api/webhooks.py
    UserSession                  <- api/webhooks.py         (Redis session)
    TranslationLogCreate         <- api/webhooks.py        -> db/models.py
    TranslationLogRead           <- api/dashboard.py        (analytics)
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# ── Enums ─────────────────────────────────────────────────────────────────────
class ConversationState(str, Enum):
    """State machine states stored in Redis per user session."""
    WAITING_FOR_IMAGE    = "waiting_for_image"
    PROCESSING           = "processing"
    WAITING_FOR_LANGUAGE = "waiting_for_language"
    TRANSLATING          = "translating"
    DONE                 = "done"
    ERROR                = "error"

class DocumentType(str, Enum):
    PRESCRIPTION       = "prescription"
    LAB_REPORT         = "lab_report"
    DISCHARGE_SUMMARY  = "discharge_summary"
    UNKNOWN            = "unknown"

# ── Twilio Webhook ─────────────────────────────────────────────────────────────
class TwilioWebhookPayload(BaseModel):
    """Parsed form data from Twilio's WhatsApp POST /webhook/whatsapp.
    
    Twilio sends application/x-www-form-urlencoded.
    Only fields SehatSamjho needs are captured; extra fields are ignored.
    Reference: https://www.twilio.com/docs/messaging/guided/webhook-request
    """
    model_config = {"extra": "ignore", "populate_by_name": True}

    From: str = Field(alias="From")                     # e.g. "whatsapp:+919876543210"
    To: str = Field(alias="To")                         # Twilio sandbox number
    Body: str = Field(default="", alias="Body")         # text content (empty for image-only)
    NumMedia: int = Field(default=0, alias="NumMedia")  # 0 or 1 for WhatsApp
    MediaUrl0: Optional[str] = Field(default=None, alias="MediaUrl0")
    MediaContentType0: Optional[str] = Field(default=None, alias="MediaContentType0")
    MessageSid: str = Field(alias="MessageSid")         # unique Twilio message ID

# ── Extraction output ──────────────────────────────────────────────────────────

class Medication(BaseModel):
    """One drug entry extracted from a prescription image."""
    name: str            
    dosage: str = ""            # e.g. "500mg"
    frequency: str = ""         # e.g. "twice daily", "BD"
    duration: str  = ""         # e.g. "5days"
    quantity: str = ""          # e.g. "10 tablets"
    instructions: str = ""       # e.g. "take after food"

class PrescriptionData(BaseModel):
    """Structured output from GPT-4o Vision extraction.
    
    All fields are optional - partial extraction is valid and expected
    when the image is blurry or partially legible.
    """
    doc_type: DocumentType = DocumentType.UNKNOWN
    medications: list[Medication] = Field(default_factory=list)
    diagnosis: str = ""
    doctor_name: str = ""
    date: str = ""      # as printed on document
    general_instructions: str = ""
    warnings: list[str] = Field(default_factory=list)
    raw_text: str = ""  # full OCR transcript

# ── Redis session ──────────────────────────────────────────────────────────────
class UserSession(BaseModel):
    """Conversation state stored in Redis per user (keypad by phone number).

    TTL = settings.session_ttl_seconds (default 30 min)
    Serialised as JSON via model_dump_json() / model_validate_json().
    """
    state: ConversationState = ConversationState.WAITING_FOR_IMAGE
    language_code: Optional[str] = None # e.g. "hi", "ta"
    language_name: Optional[str] = None # e.g. "Hindi"
    prescription: Optional[PrescriptionData] = None
    request_id: Optional[str] = None # Twilio MessageSid
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ── Database log (zero PHI) ────────────────────────────────────────────────────

class TranslationLogCreate(BaseModel):
    """Metadata row written to PostgreSQL after each interaction.
    
    PRIVACY: phone_hash is SHA-256of the raw phone string - not reversible
    No prescription content, patient name, or diagnosis is ever stored.
    """

    request_id: str         # Twilio MessageSid - unique per message
    phone_hash: str         # SHA-256(phone) - 64-char hex string
    language_code: str
    doc_type: str
    latency_ms: int
    drug_count: int = 0
    has_audio: bool = False
    status: str = "success"
    error_code: Optional[str] = None

class TranslationLogRead(TranslationLogCreate):
    """Analytics record returned by the dashboard API."""
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
