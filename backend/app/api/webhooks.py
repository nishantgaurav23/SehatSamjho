"""S4.1 + S4.2 — Webhook Endpoint & Dispatch.

POST /webhook/whatsapp: entry point for all incoming WhatsApp messages from Twilio.
Parses Twilio form body into WebhookPayload, validates HMAC signature,
generates request_id, dispatches to handler based on session state, and returns TwiML.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import validate_twilio_signature
from backend.app.db.models import InteractionLog, InteractionStatus
from backend.app.db.redis import get_redis
from backend.app.models.schemas import SessionState, SessionStatus, WebhookPayload
from backend.app.services.whatsapp import (
    parse_language_selection,
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


async def _run_pipeline(
    payload: WebhookPayload, session: SessionState, request_id: str, redis
) -> None:
    """Placeholder pipeline — will be replaced in S10.1 with full extraction/translation/TTS."""
    with logger.contextualize(request_id=request_id):
        logger.info("Pipeline placeholder invoked (not yet implemented)")
        await send_text_message(
            payload.from_number,
            "Translation pipeline coming soon! Your session has been reset "
            "so you can start a new conversation.",
        )
        await _delete_session(payload.from_number, redis)
        logger.info("Session cleaned up after pipeline placeholder")


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
