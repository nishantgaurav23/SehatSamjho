"""
app/services/extraction.py — GPT-4o Vision prescription extraction

What it does:
    Sends a medical document image URL to GPT-4o Vision and returns a structured
    PrescriptionData object plus a confidence score.

Integration:
    extract_prescription() ← api/webhooks.py  (called in WAITING_FOR_IMAGE state)
    PrescriptionData       → api/webhooks.py  (formatted into WhatsApp reply)
    _call_openai_with_retry has tenacity retry for transient OpenAI errors only.
    NotMedicalDocumentError / ImageNotReadableError are semantic errors — no retry.
"""

import json
from typing import Any

from loguru import logger
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.schemas import DocumentType, Medication, PrescriptionData


# ── Custom exceptions ─────────────────────────────────────────────────────────

class NotMedicalDocumentError(Exception):
    """Raised when GPT-4o determines the image is not a medical document."""


class ImageNotReadableError(Exception):
    """Raised when the image is too blurry or confidence is too low for reliable extraction."""


# ── OpenAI singleton ──────────────────────────────────────────────────────────

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Return module-level AsyncOpenAI singleton, creating it on first call."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            timeout=settings.openai_timeout_seconds,
        )
    return _client


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a medical document analysis assistant for India. \
Analyze the provided image and extract structured information.

Return ONLY valid JSON with this exact structure:
{
  "is_medical_document": <bool>,
  "is_legible": <bool>,
  "doc_type": "prescription|lab_report|discharge_summary|unknown",
  "medications": [
    {
      "name": "<drug name>",
      "dosage": "<e.g. 500mg>",
      "frequency": "<e.g. twice daily>",
      "duration": "<e.g. 5 days>",
      "quantity": "<e.g. 10 tablets>",
      "instructions": "<e.g. after food>",
      "confidence": "high|low"
    }
  ],
  "diagnosis": "<diagnosis or empty string>",
  "doctor_name": "<name or empty string>",
  "date": "<date as printed or empty string>",
  "general_instructions": "<general advice or empty string>",
  "warnings": ["<warnings or drug interactions>"],
  "raw_text": "<full OCR transcription>",
  "overall_confidence": <float 0.0-1.0>
}

Rules:
- If not a medical document: set is_medical_document=false, other fields to defaults.
- If unreadable: set is_legible=false and overall_confidence below 0.2.
- Never invent information not visible in the image.
- Indian drug brand names are common — preserve them exactly as written.
- Return ONLY the JSON object, no explanation."""


# ── Public API ────────────────────────────────────────────────────────────────

async def extract_prescription(
    image_url: str, request_id: str
) -> tuple[PrescriptionData, float]:
    """Extract structured prescription data from a medical document image.

    Args:
        image_url:  Publicly accessible URL of the image (from Twilio).
        request_id: Twilio MessageSid for log correlation.

    Returns:
        Tuple of (PrescriptionData, confidence_float).

    Raises:
        NotMedicalDocumentError: Image is not a medical document.
        ImageNotReadableError:   Image is too blurry or confidence < 0.2.
    """
    log = logger.bind(request_id=request_id)
    log.info(f"Extracting prescription from image: {image_url[:60]}...")

    client = _get_client()
    data = await _call_openai_with_retry(client, image_url, request_id)

    if not data.get("is_medical_document", True):
        raise NotMedicalDocumentError("Image is not a medical document")

    if not data.get("is_legible", True) or data.get("overall_confidence", 1.0) < 0.2:
        raise ImageNotReadableError("Image is unreadable or confidence too low")

    prescription = _parse_to_pydantic(data)
    confidence = _compute_confidence(data)

    log.info(
        f"Extraction complete: {len(prescription.medications)} meds, "
        f"doc_type={prescription.doc_type.value}, confidence={confidence:.2f}"
    )
    return prescription, confidence


# ── Private: retried API call ─────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=3),
    reraise=True,
)
async def _call_openai_with_retry(
    client: AsyncOpenAI, image_url: str, request_id: str
) -> dict[str, Any]:
    """Call GPT-4o Vision API and return parsed JSON dict.

    Retry handles transient network/rate-limit errors from OpenAI.
    Semantic errors (non-medical, unreadable) are detected in extract_prescription()
    after this returns successfully, and are never retried.
    """
    logger.bind(request_id=request_id).debug("Calling GPT-4o Vision API")

    response = await client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=settings.openai_max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_url, "detail": "high"},
                    },
                    {
                        "type": "text",
                        "text": "Extract all medical information from this document.",
                    },
                ],
            },
        ],
    )
    return json.loads(response.choices[0].message.content)


# ── Private: parsing helpers ──────────────────────────────────────────────────

def _parse_to_pydantic(data: dict[str, Any]) -> PrescriptionData:
    """Map GPT-4o JSON output to the PrescriptionData Pydantic model."""
    doc_type_str = data.get("doc_type", "unknown")
    try:
        doc_type = DocumentType(doc_type_str)
    except ValueError:
        doc_type = DocumentType.UNKNOWN

    medications: list[Medication] = []
    for med in data.get("medications", []):
        name = med.get("name", "").strip()
        if not name:
            continue  # skip medications with empty names — GPT hallucination guard
        medications.append(
            Medication(
                name=name,
                dosage=med.get("dosage", ""),
                frequency=med.get("frequency", ""),
                duration=med.get("duration", ""),
                quantity=med.get("quantity", ""),
                instructions=med.get("instructions", ""),
            )
        )

    return PrescriptionData(
        doc_type=doc_type,
        medications=medications,
        diagnosis=data.get("diagnosis", ""),
        doctor_name=data.get("doctor_name", ""),
        date=data.get("date", ""),
        general_instructions=data.get("general_instructions", ""),
        warnings=data.get("warnings", []),
        raw_text=data.get("raw_text", ""),
    )


def _compute_confidence(data: dict[str, Any]) -> float:
    """Compute weighted confidence score from GPT-4o output.

    Formula:
        60% weight: overall_confidence reported by GPT-4o
        40% weight: per-medication average (high → 1.0, low → 0.5)

    If no medications, the full weight falls on overall_confidence.
    """
    overall = float(data.get("overall_confidence", 0.0))

    meds = data.get("medications", [])
    valid_meds = [m for m in meds if m.get("name", "").strip()]

    if not valid_meds:
        return overall

    confidence_map = {"high": 1.0, "low": 0.5}
    med_avg = sum(
        confidence_map.get(m.get("confidence", "low"), 0.5) for m in valid_meds
    ) / len(valid_meds)

    return 0.6 * overall + 0.4 * med_avg
