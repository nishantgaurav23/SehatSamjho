"""
app/api/webhooks.py — Twilio WhatsApp webhook handler

What it does:
    Receives POST /webhook/whatsapp from Twilio, validates the HMAC-SHA1
    signature, and drives a Redis-backed conversation state machine through
    language selection → image upload → GPT-4o extraction → reply.

State machine:
    WAITING_FOR_LANGUAGE → (user picks language) → WAITING_FOR_IMAGE
    WAITING_FOR_IMAGE    → (user sends image)    → PROCESSING → DONE
    DONE / ERROR         → (new message)          → WAITING_FOR_LANGUAGE (reset)
    PROCESSING           → (any message)          → "still processing" reply

Integration:
    registered in main.py at POST /webhook/whatsapp
    uses get_db()    (db/database.py)  for metadata logging
    uses get_redis() (db/redis.py)     for session state
    calls extract_prescription() (services/extraction.py)
    calls send_text_message()    (services/whatsapp.py)
"""

import time

from fastapi import APIRouter, Depends, Request, Response
from loguru import logger
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_phone, verify_twilio_signature
from app.db.database import get_db
from app.db.models import TranslationLog
from app.db.redis import get_redis
from app.models.schemas import ConversationState, TwilioWebhookPayload, UserSession
from app.services.extraction import (
    ImageNotReadableError,
    NotMedicalDocumentError,
    extract_prescription,
)
from app.services.whatsapp import (
    parse_language_selection,
    send_language_selection,
    send_text_message,
)

router = APIRouter()

_SESSION_PREFIX = "session:"
_SESSION_TTL = settings.session_ttl_seconds


# ── Session helpers ───────────────────────────────────────────────────────────

async def _get_session(r: Redis, phone_hash: str) -> UserSession:
    """Load user session from Redis, or return a fresh session if not found."""
    raw = await r.get(f"{_SESSION_PREFIX}{phone_hash}")
    if raw:
        return UserSession.model_validate_json(raw)
    return UserSession()


async def _save_session(r: Redis, phone_hash: str, session: UserSession) -> None:
    """Persist user session to Redis with TTL."""
    await r.setex(
        f"{_SESSION_PREFIX}{phone_hash}",
        _SESSION_TTL,
        session.model_dump_json(),
    )


# ── Webhook route ─────────────────────────────────────────────────────────────

@router.post("/webhook/whatsapp")
async def webhook_whatsapp(
    request: Request,
    r: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Entry point for all inbound Twilio WhatsApp messages.

    1. Parse form data into TwilioWebhookPayload.
    2. Verify Twilio HMAC-SHA1 signature (skipped in dev mode).
    3. Look up Redis session by hashed phone number.
    4. Dispatch to the correct state handler.
    5. Return HTTP 200 (Twilio requires 200 to avoid retries).
    """
    form_data = dict(await request.form())

    # Validate Twilio signature (validate_twilio_signature=False skips in dev)
    signature = request.headers.get("X-Twilio-Signature", "")
    if not verify_twilio_signature(str(request.url), form_data, signature):
        logger.warning("Rejected webhook: invalid Twilio signature")
        return Response(status_code=403)

    payload = TwilioWebhookPayload(**form_data)
    phone_hash = hash_phone(payload.From)

    logger.bind(request_id=payload.MessageSid, phone_hash=phone_hash[:8]).info(
        f"Webhook received: state machine entry, NumMedia={payload.NumMedia}"
    )

    session = await _get_session(r, phone_hash)
    await _dispatch(payload, session, phone_hash, r, db)

    return Response(status_code=200)


# ── State machine dispatcher ──────────────────────────────────────────────────

async def _dispatch(
    payload: TwilioWebhookPayload,
    session: UserSession,
    phone_hash: str,
    r: Redis,
    db: AsyncSession,
) -> None:
    """Route the incoming message to the correct handler based on session state."""
    state = session.state

    if state in (
        ConversationState.WAITING_FOR_LANGUAGE,
        ConversationState.DONE,
        ConversationState.ERROR,
    ):
        await _handle_language_state(payload, session, phone_hash, r)

    elif state == ConversationState.WAITING_FOR_IMAGE:
        await _handle_image_state(payload, session, phone_hash, r, db)

    elif state == ConversationState.PROCESSING:
        await send_text_message(
            payload.From,
            "⏳ Your document is still being processed. Please wait a moment.",
            request_id=payload.MessageSid,
        )

    else:
        # TRANSLATING or unknown state — reset to fresh session
        logger.warning(
            f"Unexpected state {state!r} — resetting session for {phone_hash[:8]}"
        )
        session = UserSession()
        await _save_session(r, phone_hash, session)
        await send_language_selection(payload.From, request_id=payload.MessageSid)


async def _handle_language_state(
    payload: TwilioWebhookPayload,
    session: UserSession,
    phone_hash: str,
    r: Redis,
) -> None:
    """Handle messages when the user needs to select a language."""
    selection = parse_language_selection(payload.Body)

    if selection is None:
        # Unrecognized input — reset and resend the language menu
        session = UserSession()
        await _save_session(r, phone_hash, session)
        await send_language_selection(payload.From, request_id=payload.MessageSid)
        return

    language_name, language_code = selection
    session.state = ConversationState.WAITING_FOR_IMAGE
    session.language_code = language_code
    session.language_name = language_name
    await _save_session(r, phone_hash, session)

    await send_text_message(
        payload.From,
        f"✅ *{language_name}* selected.\n\n"
        "📷 Please send a clear photo of your prescription, lab report, "
        "or medical document.",
        request_id=payload.MessageSid,
    )


async def _handle_image_state(
    payload: TwilioWebhookPayload,
    session: UserSession,
    phone_hash: str,
    r: Redis,
    db: AsyncSession,
) -> None:
    """Handle messages when the user is expected to send a medical document image."""
    if payload.NumMedia == 0:
        await send_text_message(
            payload.From,
            "📷 Please send a *photo* of your medical document (not text).\n\n"
            "Take a clear, well-lit photo of your prescription or lab report.",
            request_id=payload.MessageSid,
        )
        return

    # Image received — mark as PROCESSING and start extraction
    session.state = ConversationState.PROCESSING
    session.request_id = payload.MessageSid
    await _save_session(r, phone_hash, session)

    await send_text_message(
        payload.From,
        "⏳ Received your document! Translating now, please wait...",
        request_id=payload.MessageSid,
    )

    start_ms = int(time.monotonic() * 1000)

    try:
        prescription, confidence = await extract_prescription(
            payload.MediaUrl0, payload.MessageSid
        )
        latency_ms = int(time.monotonic() * 1000) - start_ms

        session.state = ConversationState.DONE
        session.prescription = prescription
        await _save_session(r, phone_hash, session)

        reply = _format_extraction_reply(
            prescription, session.language_name or "English"
        )
        await send_text_message(payload.From, reply, request_id=payload.MessageSid)

        await _log_interaction(
            db,
            request_id=payload.MessageSid,
            phone_hash=phone_hash,
            language_code=session.language_code or "en",
            doc_type=prescription.doc_type.value,
            latency_ms=latency_ms,
            confidence_avg=confidence,
            drug_count=len(prescription.medications),
            status="success",
        )

    except NotMedicalDocumentError:
        latency_ms = int(time.monotonic() * 1000) - start_ms
        session.state = ConversationState.WAITING_FOR_IMAGE
        await _save_session(r, phone_hash, session)

        await send_text_message(
            payload.From,
            "❌ This doesn't look like a medical document.\n\n"
            "Please send a photo of a *prescription*, *lab report*, "
            "or *discharge summary*.",
            request_id=payload.MessageSid,
        )
        await _log_interaction(
            db,
            request_id=payload.MessageSid,
            phone_hash=phone_hash,
            language_code=session.language_code or "en",
            doc_type="unknown",
            latency_ms=latency_ms,
            status="error",
            error_code="not_medical_document",
        )

    except ImageNotReadableError:
        latency_ms = int(time.monotonic() * 1000) - start_ms
        session.state = ConversationState.WAITING_FOR_IMAGE
        await _save_session(r, phone_hash, session)

        await send_text_message(
            payload.From,
            "📷 The image is too blurry or unclear to read.\n\n"
            "Please take a new photo with:\n"
            "• Good lighting\n"
            "• The document fully in frame\n"
            "• Camera held steady",
            request_id=payload.MessageSid,
        )
        await _log_interaction(
            db,
            request_id=payload.MessageSid,
            phone_hash=phone_hash,
            language_code=session.language_code or "en",
            doc_type="unknown",
            latency_ms=latency_ms,
            status="error",
            error_code="image_not_readable",
        )

    except Exception as exc:
        latency_ms = int(time.monotonic() * 1000) - start_ms
        logger.exception(
            f"Unexpected extraction error for request {payload.MessageSid}: {exc}"
        )
        session.state = ConversationState.WAITING_FOR_IMAGE
        await _save_session(r, phone_hash, session)

        await send_text_message(
            payload.From,
            "😔 Something went wrong while processing your document.\n\n"
            "Please try again in a moment.",
            request_id=payload.MessageSid,
        )
        await _log_interaction(
            db,
            request_id=payload.MessageSid,
            phone_hash=phone_hash,
            language_code=session.language_code or "en",
            doc_type="unknown",
            latency_ms=latency_ms,
            status="error",
            error_code="extraction_failed",
        )


# ── Reply formatter ───────────────────────────────────────────────────────────

def _format_extraction_reply(prescription, language_name: str) -> str:
    """Format extracted prescription data as a readable WhatsApp message.

    Day 1: English extraction summary.
    Full translation in the user's language comes in Day 2 (translation.py).
    """
    lines = ["📋 *Document Summary*", ""]
    lines.append(f"*Type:* {prescription.doc_type.value.replace('_', ' ').title()}")

    if prescription.doctor_name:
        lines.append(f"*Doctor:* {prescription.doctor_name}")
    if prescription.date:
        lines.append(f"*Date:* {prescription.date}")
    if prescription.diagnosis:
        lines.append(f"*Diagnosis:* {prescription.diagnosis}")

    lines.append("")

    _sep = " \u2014 "   # em dash separator; defined outside f-string (Python 3.11 compat)
    _bullet = "\u2022"  # bullet; same reason

    if prescription.medications:
        lines.append(f"💊 *Medicines ({len(prescription.medications)}):*")
        for med in prescription.medications:
            parts = [med.name]
            if med.dosage:
                parts.append(med.dosage)
            details = []
            if med.frequency:
                details.append(med.frequency)
            if med.duration:
                details.append(f"for {med.duration}")
            if details:
                parts.append(", ".join(details))
            lines.append(f"  {_bullet} {_sep.join(parts)}")
            if med.instructions:
                lines.append(f"    _{med.instructions}_")

    if prescription.general_instructions:
        lines.extend(["", f"📝 *Instructions:* {prescription.general_instructions}"])

    if prescription.warnings:
        lines.extend(["", "⚠️ *Warnings:*"])
        for w in prescription.warnings:
            lines.append(f"  {_bullet} {w}")

    lines.extend([
        "",
        "---",
        "_⚕️ This is an automated extraction. Always follow your doctor's advice._",
        f"_Note: Full translation in {language_name} coming in next update._",
    ])

    return "\n".join(lines)


# ── DB logger ─────────────────────────────────────────────────────────────────

async def _log_interaction(
    db: AsyncSession,
    *,
    request_id: str,
    phone_hash: str,
    language_code: str,
    doc_type: str,
    latency_ms: int,
    confidence_avg: float | None = None,
    drug_count: int = 0,
    has_audio: bool = False,
    status: str = "success",
    error_code: str | None = None,
) -> None:
    """Write a metadata row to PostgreSQL. Wrapped in try/except — never crashes the handler."""
    try:
        row = TranslationLog(
            request_id=request_id,
            phone_hash=phone_hash,
            language_code=language_code,
            doc_type=doc_type,
            latency_ms=latency_ms,
            confidence_avg=confidence_avg,
            drug_count=drug_count,
            has_audio=has_audio,
            status=status,
            error_code=error_code,
        )
        db.add(row)
    except Exception as exc:
        logger.error(f"Failed to log interaction {request_id}: {exc}")
