"""S4.1 + S4.2 — Webhook Endpoint & Dispatch.

POST /webhook/whatsapp: entry point for all incoming WhatsApp messages from Twilio.
Parses Twilio form body into WebhookPayload, validates HMAC signature,
generates request_id, dispatches to handler based on session state, and returns TwiML.
"""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import validate_twilio_signature
from backend.app.db.database import AsyncSessionLocal
from backend.app.db.models import InteractionLog, InteractionStatus
from backend.app.db.redis import get_redis
from backend.app.models.schemas import (
    DrugInfo,
    PrescriptionData,
    SessionState,
    SessionStatus,
    TranslationResult,
    WebhookPayload,
)
from backend.app.services.drug_lookup import enrich_prescription
from backend.app.services.extraction import (
    ExtractionError,
    ImageNotReadableError,
    NotMedicalDocumentError,
    extract_prescription,
)
from backend.app.services.glossary import format_glossary_context, lookup_terms
from backend.app.services.tts import generate_and_deliver_audio
from backend.app.services.translation import TranslationError, simplify_and_translate
from backend.app.services.whatsapp import (
    parse_language_selection,
    send_audio_message_with_fallback,
    send_language_selection,
    send_more_languages,
    send_text_message,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# TwiML response constant
# ---------------------------------------------------------------------------
TWIML_EMPTY = "<Response/>"
TWIML_MEDIA_TYPE = "text/xml"

# Patient-friendly error message (never expose internals)
ERROR_MESSAGE = (
    "We're sorry, something went wrong while processing your message. "
    "Please try again in a moment."
)

# ---------------------------------------------------------------------------
# S10.4 Pipeline error message constants
# ---------------------------------------------------------------------------
NOT_MEDICAL_DOC_MESSAGE = (
    "This doesn't appear to be a medical document. "
    "Please send a photo of a prescription, lab report, or discharge summary."
)

IMAGE_NOT_READABLE_MESSAGE = (
    "We couldn't read your image clearly. "
    "Please try again with better lighting and make sure the text is in focus."
)

TRANSLATION_ERROR_MESSAGE = (
    "We had trouble translating your prescription. " "Please try sending the image again."
)

EXTRACTION_ERROR_MESSAGE = (
    "We had trouble reading your prescription. " "Please try sending a clearer photo."
)

GENERIC_PIPELINE_ERROR_MESSAGE = (
    "We're sorry, something went wrong while processing your prescription. "
    "Please try again in a moment."
)

# ---------------------------------------------------------------------------
# S4.3 Welcome message constant
# ---------------------------------------------------------------------------
WELCOME_MESSAGE = (
    "Welcome to SehatSamjho!\n\n"
    "We help you understand your prescriptions by translating them "
    "into plain language and audio in your preferred language.\n\n"
    "Your privacy matters: we do not store any personal health data.\n\n"
    "Please choose your language to get started."
)

# ---------------------------------------------------------------------------
# S4.4 Language state constants
# ---------------------------------------------------------------------------
IMAGE_PROMPT_MESSAGE = (
    "Great choice! Now please send a photo of your prescription "
    "and we will translate it for you."
)

LANGUAGE_NOT_RECOGNISED_MESSAGE = (
    "Sorry, we didn't recognise that language choice. "
    "Please select a number from the menu or type a language name."
)

# ---------------------------------------------------------------------------
# S4.5 Image state constants
# ---------------------------------------------------------------------------
PROCESSING_ACK_MESSAGE = (
    "Got it! We're now translating your prescription. "
    "This usually takes about 20\u201330 seconds \u2014 please wait."
)

NO_IMAGE_MESSAGE = (
    "We didn't receive an image. Please send a photo of your prescription "
    "so we can translate it for you."
)

UNSUPPORTED_MEDIA_MESSAGE = (
    "Sorry, we only support photo/image files (JPEG, PNG, etc.). "
    "Please send a photo of your prescription instead."
)

# ---------------------------------------------------------------------------
# S4.2 Constants
# ---------------------------------------------------------------------------
SESSION_KEY_PREFIX = "session:"
SESSION_TTL_SECONDS = 1800  # 30 minutes
PROCESSING_MESSAGE = "Your prescription is still being processed. Please wait a moment."


# ---------------------------------------------------------------------------
# S4.2 FR-8: Session key helper
# ---------------------------------------------------------------------------


def _session_key(from_number: str) -> str:
    """Return the Redis key for a phone number's session."""
    return f"{SESSION_KEY_PREFIX}{from_number}"


# ---------------------------------------------------------------------------
# S4.2 FR-4: Save session helper
# ---------------------------------------------------------------------------


async def _save_session(phone_number: str, session: SessionState, redis) -> None:
    """Serialize SessionState to JSON and store in Redis with TTL."""
    key = _session_key(phone_number)
    await redis.set(key, session.model_dump_json(), ex=SESSION_TTL_SECONDS)


# ---------------------------------------------------------------------------
# S4.2 FR-5: Delete session helper
# ---------------------------------------------------------------------------


async def _delete_session(phone_number: str, redis) -> None:
    """Remove the session key from Redis."""
    key = _session_key(phone_number)
    await redis.delete(key)


# ---------------------------------------------------------------------------
# S4.2 FR-1: Load session from Redis
# ---------------------------------------------------------------------------


async def _load_session(phone_number: str, redis) -> SessionState | None:
    """Load and deserialize session from Redis.

    Returns None if key does not exist.
    On corrupted JSON: logs warning, deletes key, returns None.
    """
    key = _session_key(phone_number)
    raw = await redis.get(key)

    if raw is None:
        return None

    try:
        return SessionState.model_validate_json(raw)
    except Exception:
        logger.warning("Corrupted session JSON, deleting key={key}", key=key)
        await redis.delete(key)
        return None


# ---------------------------------------------------------------------------
# S4.2 FR-7: Handler stubs (implemented in S4.3–S4.5)
# ---------------------------------------------------------------------------


async def _handle_welcome_state(payload: WebhookPayload, request_id: str, redis) -> None:
    """S4.3: Send welcome/consent message + language selection, create session."""
    with logger.contextualize(request_id=request_id):
        logger.info("Handling welcome state for new user")

        # FR-1: Send welcome/consent message
        await send_text_message(payload.from_number, WELCOME_MESSAGE)
        logger.info("Welcome message sent")

        # FR-2: Send language selection menu
        await send_language_selection(payload.from_number)
        logger.info("Language selection sent")

        # FR-3: Create session with WAITING_FOR_LANGUAGE status
        session = SessionState(
            status=SessionStatus.WAITING_FOR_LANGUAGE,
            language_code=None,
            language_name=None,
            request_id=request_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await _save_session(payload.from_number, session, redis)
        logger.info("Session created with status=WAITING_FOR_LANGUAGE")


async def _handle_language_state(
    payload: WebhookPayload, session: SessionState, request_id: str, redis
) -> None:
    """S4.4: Parse language selection, update session, or re-send menu."""
    with logger.contextualize(request_id=request_id):
        logger.info("Handling language state")

        # FR-4: Check for "More languages" request before parsing
        if payload.body.strip() == "9":
            logger.info("User requested more languages")
            await send_more_languages(payload.from_number)
            await send_language_selection(payload.from_number)
            return

        # FR-1: Parse language from message body
        result = parse_language_selection(payload.body)

        if result is not None:
            # FR-2: Valid language — update session
            language_name, language_code = result
            logger.info(
                "Language selected: name={name}, code={code}",
                name=language_name,
                code=language_code,
            )

            updated_session = SessionState(
                status=SessionStatus.WAITING_FOR_IMAGE,
                language_code=language_code,
                language_name=language_name,
                request_id=session.request_id,
                created_at=session.created_at,
            )
            await _save_session(payload.from_number, updated_session, redis)
            logger.info("Session updated to WAITING_FOR_IMAGE")

            # FR-3: Send image prompt
            await send_text_message(payload.from_number, IMAGE_PROMPT_MESSAGE)
            logger.info("Image prompt sent")
        else:
            # FR-5: Invalid input — send error and re-send menu
            logger.info("Unrecognised language input")
            await send_text_message(payload.from_number, LANGUAGE_NOT_RECOGNISED_MESSAGE)
            await send_language_selection(payload.from_number)
            logger.info("Language menu re-sent")


async def _handle_image_state(
    payload: WebhookPayload, session: SessionState, request_id: str, redis
) -> None:
    """S4.5: Validate image attachment, send ack, transition to PROCESSING, invoke pipeline."""
    with logger.contextualize(request_id=request_id):
        logger.info("Handling image state")

        # FR-7: No media attached — remind user to send a photo
        if payload.num_media == 0:
            logger.info("No media attached, sending reminder")
            await send_text_message(payload.from_number, NO_IMAGE_MESSAGE)
            return

        # FR-9: Non-image media type
        content_type = payload.media_content_type
        if content_type is None or not content_type.lower().startswith("image/"):
            logger.info(
                "Unsupported media type: content_type={ct}",
                ct=content_type,
            )
            await send_text_message(payload.from_number, UNSUPPORTED_MEDIA_MESSAGE)
            return

        # FR-3: Valid image — send acknowledgement
        logger.info("Valid image received, sending acknowledgement")
        await send_text_message(payload.from_number, PROCESSING_ACK_MESSAGE)

        # FR-5: Transition session to PROCESSING
        updated_session = SessionState(
            status=SessionStatus.PROCESSING,
            language_code=session.language_code,
            language_name=session.language_name,
            request_id=session.request_id,
            created_at=session.created_at,
        )
        await _save_session(payload.from_number, updated_session, redis)
        logger.info("Session updated to PROCESSING")

        # FR-6: Invoke pipeline placeholder
        await _run_pipeline(payload, updated_session, request_id, redis)


# ---------------------------------------------------------------------------
# S10.2 Constants
# ---------------------------------------------------------------------------
WHATSAPP_MAX_CHARS = 1600
LOW_CONFIDENCE_THRESHOLD = 0.7
LOW_CONFIDENCE_WARNING = (
    "\u26a0\ufe0f This item could not be read clearly"
    " \u2014 please verify with your doctor/pharmacist"
)
TRUNCATION_NOTE = "(Message truncated \u2014 ask for the full version)"
GREETING_LINE = "Here is your prescription summary:"


# ---------------------------------------------------------------------------
# S10.2 FR-1 through FR-6: Format reply for WhatsApp
# ---------------------------------------------------------------------------


def _format_reply(
    prescription: PrescriptionData,
    drug_info_list: list[DrugInfo | None],
    translation: TranslationResult,
    language_name: str,
) -> str:
    """Build patient-facing WhatsApp text from pipeline results.

    Constructs greeting + per-medicine cards + disclaimer.
    Output guaranteed <= 1600 characters (WhatsApp limit).
    Never includes PHI (patient_name, doctor_name).
    """
    greeting = GREETING_LINE
    disclaimer = translation.disclaimer
    summaries = translation.per_medicine_summaries

    # Edge case: empty medicines → greeting + translated_text + disclaimer
    if not prescription.medicines:
        body = f"{greeting}\n\n{translation.translated_text}\n\n{disclaimer}"
        return _enforce_limit(body, greeting, disclaimer)

    # Build per-medicine cards (full detail)
    cards = _build_medicine_cards(
        prescription.medicines, summaries, include_frequency=True, include_duration=True
    )
    body = _assemble(greeting, cards, disclaimer)
    if len(body) <= WHATSAPP_MAX_CHARS:
        return body

    # Truncation level 1: drop frequency/duration
    cards = _build_medicine_cards(
        prescription.medicines, summaries, include_frequency=False, include_duration=False
    )
    body = _assemble(greeting, cards, disclaimer)
    if len(body) <= WHATSAPP_MAX_CHARS:
        return _append_truncation_note(body)

    # Truncation level 2: also truncate per-medicine summaries
    cards = _build_medicine_cards(
        prescription.medicines, [], include_frequency=False, include_duration=False
    )
    body = _assemble(greeting, cards, disclaimer)
    if len(body) <= WHATSAPP_MAX_CHARS:
        return _append_truncation_note(body)

    # Truncation level 3: limit number of cards
    return _truncate_cards(greeting, prescription.medicines, disclaimer)


def _build_medicine_cards(
    medicines,
    summaries: list[str],
    include_frequency: bool = True,
    include_duration: bool = True,
) -> list[str]:
    """Build a list of card strings, one per medicine."""
    cards = []
    for i, med in enumerate(medicines):
        lines = [f"\u2022 {med.medicine_name}"]
        if med.dosage:
            lines.append(f"  Dosage: {med.dosage}")
        if include_frequency and med.frequency:
            lines.append(f"  Frequency: {med.frequency}")
        if include_duration and med.duration:
            lines.append(f"  Duration: {med.duration}")
        if i < len(summaries) and summaries[i]:
            lines.append(f"  {summaries[i]}")
        if med.confidence is not None and med.confidence < LOW_CONFIDENCE_THRESHOLD:
            lines.append(f"  {LOW_CONFIDENCE_WARNING}")
        cards.append("\n".join(lines))
    return cards


def _assemble(greeting: str, cards: list[str], disclaimer: str) -> str:
    """Combine greeting, cards, and disclaimer into a single message."""
    card_block = "\n\n".join(cards)
    return f"{greeting}\n\n{card_block}\n\n{disclaimer}"


def _append_truncation_note(body: str) -> str:
    """Add truncation note, ensuring total stays within limit."""
    with_note = f"{body}\n\n{TRUNCATION_NOTE}"
    if len(with_note) <= WHATSAPP_MAX_CHARS:
        return with_note
    # Trim body to fit note
    available = WHATSAPP_MAX_CHARS - len(f"\n\n{TRUNCATION_NOTE}")
    return f"{body[:available]}\n\n{TRUNCATION_NOTE}"


def _enforce_limit(body: str, greeting: str, disclaimer: str) -> str:
    """Ensure body fits within WhatsApp limit."""
    if len(body) <= WHATSAPP_MAX_CHARS:
        return body
    # Keep greeting + disclaimer, truncate middle
    available = (
        WHATSAPP_MAX_CHARS - len(greeting) - len(disclaimer) - len(f"\n\n\n\n{TRUNCATION_NOTE}")
    )
    middle = body[len(greeting) + 2 : len(greeting) + 2 + max(available, 0)]
    return f"{greeting}\n\n{middle}\n\n{disclaimer}\n\n{TRUNCATION_NOTE}"


def _truncate_cards(greeting: str, medicines, disclaimer: str) -> str:
    """Last-resort truncation: include as many name-only cards as fit."""
    overhead = len(greeting) + len(disclaimer) + len(f"\n\n\n\n{TRUNCATION_NOTE}")
    available = WHATSAPP_MAX_CHARS - overhead
    card_lines = []
    for med in medicines:
        line = f"\u2022 {med.medicine_name}"
        if med.dosage:
            line += f" ({med.dosage})"
        if med.confidence is not None and med.confidence < LOW_CONFIDENCE_THRESHOLD:
            line += f"\n  {LOW_CONFIDENCE_WARNING}"
        candidate = "\n".join(card_lines + [line])
        if len(candidate) > available:
            break
        card_lines.append(line)

    card_block = "\n".join(card_lines)
    return f"{greeting}\n\n{card_block}\n\n{disclaimer}\n\n{TRUNCATION_NOTE}"


# ---------------------------------------------------------------------------
# S10.3 Constants
# ---------------------------------------------------------------------------
AUDIO_MAX_CHARS = 2000
AUDIO_TRUNCATION_NOTE = "For full details, please read the text message."

# Regex: emoji + variation selectors + ZWJ
_EMOJI_RE = re.compile(
    "[\U0001f600-\U0001f64f"
    "\U0001f300-\U0001f5ff"
    "\U0001f680-\U0001f6ff"
    "\U0001f1e0-\U0001f1ff"
    "\U00002702-\U000027b0"
    "\U000024c2-\U0001f251"
    "\U0000fe0f"
    "\U0000200d"
    "\U00002600-\U000026ff"
    "\U0000231a-\U0000231b"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f"
    "\U0001fa70-\U0001faff"
    "]+"
)


# ---------------------------------------------------------------------------
# S10.3 FR-2: Strip emoji, markdown, bullets, special characters
# ---------------------------------------------------------------------------


def _strip_for_speech(text: str) -> str:
    """Remove emoji, markdown formatting, bullet points, and special Unicode."""
    # Remove emoji
    result = _EMOJI_RE.sub("", text)
    # Remove markdown: bold, italic, code, heading markers
    result = result.replace("**", "")
    result = result.replace("`", "")
    result = re.sub(r"(?<!\w)_(\S)", r"\1", result)  # leading underscore (italic)
    result = re.sub(r"(\S)_(?!\w)", r"\1", result)  # trailing underscore (italic)
    # Remove heading markers at line start
    lines = result.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#"):
            stripped = re.sub(r"^#+\s*", "", stripped)
        # Remove bullet points at line start
        if stripped.startswith("\u2022"):
            stripped = stripped[1:].lstrip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            stripped = stripped[2:].lstrip()
        cleaned_lines.append(stripped)
    result = "\n".join(cleaned_lines)
    # Remove warning symbols and decorative em-dashes
    result = result.replace("\u26a0", "")
    result = result.replace("\u2014", ",")  # em-dash → comma for speech
    # Clean up multiple spaces/newlines
    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# ---------------------------------------------------------------------------
# S10.3 FR-3: Build spoken sentences for medicines
# ---------------------------------------------------------------------------


def _build_spoken_medicines(medicines, summaries: list[str]) -> str:
    """Convert medicine entries into flowing spoken text."""
    parts = []
    for i, med in enumerate(medicines):
        # Medicine name
        sentence = med.medicine_name
        # Dosage in spoken form
        if med.dosage:
            sentence += f", dosage is {med.dosage}"
        # Frequency in spoken form
        if med.frequency:
            sentence += f", to be taken {med.frequency}"
        # Duration in spoken form
        if med.duration:
            sentence += f", for {med.duration}"
        sentence += "."
        # Per-medicine summary
        if i < len(summaries) and summaries[i]:
            clean_summary = _strip_for_speech(summaries[i])
            if clean_summary:
                sentence += f" {clean_summary}."

        # Prefix with "Next medicine:" for 2nd+ medicines
        if i > 0 and len(medicines) > 1:
            sentence = f"Next medicine: {sentence}"

        parts.append(sentence)

    return " ".join(parts)


# ---------------------------------------------------------------------------
# S10.3 FR-5: Enforce TTS length limit
# ---------------------------------------------------------------------------


def _enforce_audio_limit(text: str) -> str:
    """Cap text at AUDIO_MAX_CHARS, truncating at sentence boundary."""
    if len(text) <= AUDIO_MAX_CHARS:
        return text

    # Reserve space for fallback note
    note_space = len(f" {AUDIO_TRUNCATION_NOTE}")
    available = AUDIO_MAX_CHARS - note_space

    truncated = text[:available]

    # Find last sentence boundary (period followed by space or end)
    last_period = truncated.rfind(". ")
    if last_period == -1:
        last_period = truncated.rfind(".")
    if last_period > 0:
        truncated = truncated[: last_period + 1]
    else:
        # No sentence boundary — truncate at last word boundary
        last_space = truncated.rfind(" ")
        if last_space > 0:
            truncated = truncated[:last_space] + "."

    return f"{truncated} {AUDIO_TRUNCATION_NOTE}"


# ---------------------------------------------------------------------------
# S10.3 FR-1: _format_audio_text()
# ---------------------------------------------------------------------------


def _format_audio_text(
    prescription: PrescriptionData,
    translation: TranslationResult,
    language_name: str,
) -> str:
    """Build a spoken-friendly version of the prescription summary for TTS.

    Strips emoji, markdown, bullet points, and special characters.
    Produces flowing spoken sentences instead of card-style formatting.
    Caps output at 2000 characters for Bhashini TTS.
    Never includes PHI (patient_name, doctor_name).
    """
    # Spoken greeting
    greeting = "Here is your prescription summary."

    # Build medicine section
    if prescription.medicines:
        summaries = translation.per_medicine_summaries or []
        medicine_text = _build_spoken_medicines(prescription.medicines, summaries)
    else:
        # Fallback to translated_text when no medicines
        medicine_text = _strip_for_speech(translation.translated_text)

    # Build spoken disclaimer
    raw_disclaimer = translation.disclaimer or ""
    clean_disclaimer = _strip_for_speech(raw_disclaimer)
    if clean_disclaimer:
        disclaimer_text = f"Important note: {clean_disclaimer}"
    else:
        disclaimer_text = ""

    # Assemble
    parts = [greeting, medicine_text]
    if disclaimer_text:
        parts.append(disclaimer_text)
    assembled = " ".join(p for p in parts if p)

    # Final cleanup: strip any remaining artifacts
    assembled = _strip_for_speech(assembled)

    # Enforce length limit
    return _enforce_audio_limit(assembled)


def _handle_pipeline_error(exc: Exception) -> str:
    """Map a pipeline exception to a patient-friendly WhatsApp error message.

    isinstance checks are ordered most-specific-first so subclasses match correctly.
    Never exposes internals, stack traces, or PHI.
    """
    if isinstance(exc, NotMedicalDocumentError):
        return NOT_MEDICAL_DOC_MESSAGE
    if isinstance(exc, ImageNotReadableError):
        return IMAGE_NOT_READABLE_MESSAGE
    if isinstance(exc, TranslationError):
        return TRANSLATION_ERROR_MESSAGE
    if isinstance(exc, ExtractionError):
        return EXTRACTION_ERROR_MESSAGE
    return GENERIC_PIPELINE_ERROR_MESSAGE


async def _run_pipeline(
    payload: WebhookPayload, session: SessionState, request_id: str, redis
) -> None:
    """S10.1: Full pipeline — extract → enrich → glossary → translate → TTS → send."""
    with logger.contextualize(request_id=request_id):
        start = time.monotonic()
        try:
            # Step 1: Extract prescription from image (GPT-4O Vision)
            logger.info("Pipeline started: extraction")
            prescription_data = await extract_prescription(
                image_url=payload.media_url,
                content_type=payload.media_content_type,
                request_id=request_id,
            )
            logger.info("Extraction complete")

            # Step 2: Enrich with drug lookup
            logger.info("Pipeline: drug enrichment")
            drug_info_list = await enrich_prescription(
                redis_client=redis,
                prescription=prescription_data,
                request_id=request_id,
            )
            logger.info("Drug enrichment complete")

            # Step 3: Glossary lookup
            logger.info("Pipeline: glossary lookup")
            medicine_terms = [m.medicine_name for m in prescription_data.medicines]
            glossary_entries = await lookup_terms(medicine_terms, session.language_code, redis)
            glossary_context = format_glossary_context(glossary_entries, session.language_name)
            logger.info("Glossary lookup complete")

            # Step 4: Translate with Claude Sonnet 4.6
            logger.info("Pipeline: translation")
            translation_result = await simplify_and_translate(
                prescription=prescription_data,
                language_name=session.language_name,
                language_code=session.language_code,
                drug_info_list=drug_info_list,
                glossary_context=glossary_context,
                request_id=request_id,
            )
            logger.info("Translation complete")

            # Step 5: Format audio text for TTS (S10.3)
            logger.info("Pipeline: formatting audio text")
            audio_text = _format_audio_text(
                prescription=prescription_data,
                translation=translation_result,
                language_name=session.language_name,
            )
            logger.info("Audio text formatted")

            # Step 6: Generate TTS audio
            logger.info("Pipeline: TTS audio generation")
            audio_url = await generate_and_deliver_audio(
                text=audio_text,
                language_code=session.language_code,
                request_id=request_id,
            )
            logger.info("TTS complete: audio_available={avail}", avail=audio_url is not None)

            # Step 7: Format and send text reply
            logger.info("Pipeline: formatting reply")
            reply_text = _format_reply(
                prescription=prescription_data,
                drug_info_list=drug_info_list,
                translation=translation_result,
                language_name=session.language_name,
            )
            logger.info("Pipeline: sending text reply")
            await send_text_message(payload.from_number, reply_text)
            logger.info("Text reply sent")

            # Step 8: Send audio if available
            if audio_url is not None:
                logger.info("Pipeline: sending audio message")
                await send_audio_message_with_fallback(
                    payload.from_number,
                    audio_url,
                    fallback_text=audio_text,
                )
                logger.info("Audio message sent")

            # Compute metrics
            latency_ms = int((time.monotonic() - start) * 1000)
            confidence_avg = _compute_confidence_avg(prescription_data)

            # Log interaction to DB
            logger.info("Pipeline: logging interaction")
            async with AsyncSessionLocal() as db:
                await _log_interaction(
                    phone_number=payload.from_number,
                    language_code=session.language_code,
                    status=InteractionStatus.SUCCESS,
                    request_id=request_id,
                    db=db,
                    confidence_avg=confidence_avg,
                    latency_ms=latency_ms,
                )
                await db.commit()
            logger.info(
                "Pipeline complete: latency_ms={lat}, confidence_avg={conf}",
                lat=latency_ms,
                conf=confidence_avg,
            )

        except Exception as exc:
            # S10.4: Map exception to patient-friendly message
            error_msg = _handle_pipeline_error(exc)
            error_code = type(exc).__name__[:100]

            logger.error(
                "Pipeline error: error_code={code}",
                code=error_code,
            )

            # Send error message to user (gracefully handle send failure)
            try:
                await send_text_message(payload.from_number, error_msg)
            except Exception:
                logger.error("Failed to send pipeline error message to user")

            # Log interaction with error status
            latency_ms = int((time.monotonic() - start) * 1000)
            try:
                async with AsyncSessionLocal() as db:
                    await _log_interaction(
                        phone_number=payload.from_number,
                        language_code=session.language_code,
                        status=InteractionStatus.ERROR,
                        request_id=request_id,
                        db=db,
                        latency_ms=latency_ms,
                        error_code=error_code,
                    )
                    await db.commit()
            except Exception:
                logger.error("Failed to log pipeline error interaction")

        finally:
            # Always clean up session (success or failure)
            await _delete_session(payload.from_number, redis)
            logger.info("Session cleaned up")


def _compute_confidence_avg(prescription: PrescriptionData) -> float | None:
    """Compute average confidence from medicine entries, or None if empty."""
    confidences = [m.confidence for m in prescription.medicines if m.confidence is not None]
    if not confidences:
        return None
    return sum(confidences) / len(confidences)


# ---------------------------------------------------------------------------
# S4.6 FR-1: Hash phone number (SHA-256, zero PHI)
# ---------------------------------------------------------------------------


def _hash_phone(phone_number: str) -> str:
    """Return the SHA-256 hex digest of a phone number string."""
    return hashlib.sha256(phone_number.encode()).hexdigest()


# ---------------------------------------------------------------------------
# S4.6 FR-2: Log interaction to interaction_log table
# ---------------------------------------------------------------------------


async def _log_interaction(
    phone_number: str,
    language_code: str,
    status: InteractionStatus,
    request_id: str,
    db: AsyncSession,
    doc_type: str = "prescription",
    confidence_avg: float | None = None,
    latency_ms: int | None = None,
    error_code: str | None = None,
) -> None:
    """Create an InteractionLog row and flush it via the async DB session.

    The phone number is SHA-256 hashed before storage — raw phone numbers
    are never persisted or logged.
    """
    phone_hash = _hash_phone(phone_number)

    with logger.contextualize(request_id=request_id):
        try:
            log_entry = InteractionLog(
                phone_hash=phone_hash,
                language_code=language_code,
                doc_type=doc_type,
                status=status.value,
                confidence_avg=confidence_avg,
                latency_ms=latency_ms,
                error_code=error_code,
            )
            db.add(log_entry)
            await db.flush()

            logger.info(
                "Interaction logged: status={status}, language={lang}, doc_type={doc}",
                status=status.value,
                lang=language_code,
                doc=doc_type,
            )
        except Exception:
            logger.error(
                "Failed to log interaction: request_id={rid}, phone_hash={ph}",
                rid=request_id,
                ph=phone_hash,
            )
            raise


# ---------------------------------------------------------------------------
# S4.2 FR-2: Dispatch — route to handler based on SessionStatus
# ---------------------------------------------------------------------------


async def _dispatch(payload: WebhookPayload, request_id: str, redis) -> None:
    """Load session from Redis and route to the appropriate handler."""
    with logger.contextualize(request_id=request_id):
        session = await _load_session(payload.from_number, redis)

        if session is None:
            logger.info("New user — no session found, routing to welcome")
            await _handle_welcome_state(payload, request_id, redis)
            return

        status = session.status
        logger.info("Dispatch: session status={status}", status=status.value)

        if status == SessionStatus.WAITING_FOR_LANGUAGE:
            await _handle_language_state(payload, session, request_id, redis)
        elif status == SessionStatus.WAITING_FOR_IMAGE:
            await _handle_image_state(payload, session, request_id, redis)
        elif status == SessionStatus.PROCESSING:
            await send_text_message(payload.from_number, PROCESSING_MESSAGE)
        else:
            logger.error("Unknown session status={status}, resetting", status=status)
            await _delete_session(payload.from_number, redis)
            await _handle_welcome_state(payload, request_id, redis)


# ---------------------------------------------------------------------------
# FR-2 (S4.1): Parse Twilio form body into WebhookPayload
# ---------------------------------------------------------------------------


async def _parse_webhook_payload(request: Request) -> WebhookPayload:
    """Extract Twilio form fields and construct a WebhookPayload.

    Raises HTTPException(400) if From is missing or empty.
    """
    form_data = await request.form()

    from_number = form_data.get("From", "")
    if not from_number or not str(from_number).strip():
        raise HTTPException(status_code=400, detail="Missing required field: From")

    body = form_data.get("Body", "")
    raw_num_media = form_data.get("NumMedia", "0")

    try:
        num_media = int(raw_num_media)
    except (ValueError, TypeError):
        num_media = 0

    media_url = form_data.get("MediaUrl0") or None
    media_content_type = form_data.get("MediaContentType0") or None

    return WebhookPayload(
        from_number=str(from_number),
        body=str(body),
        num_media=num_media,
        media_url=str(media_url) if media_url else None,
        media_content_type=str(media_content_type) if media_content_type else None,
    )


# ---------------------------------------------------------------------------
# POST /webhook/whatsapp
# ---------------------------------------------------------------------------


@router.post(
    "/whatsapp",
    dependencies=[Depends(validate_twilio_signature)],
)
async def webhook_whatsapp(request: Request, redis=Depends(get_redis)) -> Response:
    """Handle incoming WhatsApp messages from Twilio.

    1. Generate unique request_id (UUID4) and bind to Loguru context.
    2. Parse Twilio form body into WebhookPayload.
    3. Dispatch to handler based on session state.
    4. Return TwiML <Response/> (always 200 to prevent Twilio retries).
    """
    request_id = str(uuid.uuid4())
    from_number: str | None = None

    with logger.contextualize(request_id=request_id):
        try:
            logger.info("Webhook received")

            # Try to extract from_number early for error handling
            form_data = await request.form()
            from_number = str(form_data.get("From", "")) or None

            # Parse the full payload
            payload = await _parse_webhook_payload(request)
            from_number = payload.from_number

            logger.info(
                "Parsed webhook payload: num_media={num_media}, has_body={has_body}",
                num_media=payload.num_media,
                has_body=bool(payload.body),
            )

            # S4.2: Dispatch to handler based on session state
            await _dispatch(payload, request_id, redis)

            return Response(content=TWIML_EMPTY, media_type=TWIML_MEDIA_TYPE)

        except HTTPException:
            # Re-raise HTTP exceptions (400, etc.) directly
            raise

        except Exception:
            logger.exception("Unhandled error in webhook")

            # Send error message to user if we have their number
            if from_number:
                try:
                    await send_text_message(from_number, ERROR_MESSAGE)
                except Exception:
                    logger.exception("Failed to send error message to user")

            # Always return TwiML 200 to prevent Twilio retries
            return Response(content=TWIML_EMPTY, media_type=TWIML_MEDIA_TYPE)
