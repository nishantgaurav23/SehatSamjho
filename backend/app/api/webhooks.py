"""S4.1 + S4.2 — Webhook Endpoint & Dispatch.

POST /webhook/whatsapp: entry point for all incoming WhatsApp messages from Twilio.
Parses Twilio form body into WebhookPayload, validates HMAC signature,
generates request_id, dispatches to handler based on session state, and returns TwiML.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from loguru import logger

from backend.app.core.security import validate_twilio_signature
from backend.app.db.redis import get_redis
from backend.app.models.schemas import SessionState, SessionStatus, WebhookPayload
from backend.app.services.whatsapp import send_text_message

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
    """Stub: welcome handler — will be implemented in S4.3."""
    logger.warning("_handle_welcome_state not yet implemented")
    await send_text_message(payload.from_number, "Welcome! This feature is coming soon.")


async def _handle_language_state(
    payload: WebhookPayload, session: SessionState, request_id: str, redis
) -> None:
    """Stub: language selection handler — will be implemented in S4.4."""
    logger.warning("_handle_language_state not yet implemented")
    await send_text_message(payload.from_number, "Language selection coming soon.")


async def _handle_image_state(
    payload: WebhookPayload, session: SessionState, request_id: str, redis
) -> None:
    """Stub: image handler — will be implemented in S4.5."""
    logger.warning("_handle_image_state not yet implemented")
    await send_text_message(payload.from_number, "Image processing coming soon.")


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
