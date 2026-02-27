"""
app/services/whatsapp.py — Twilio WhatsApp client for SehatSamjho

What it does:
    Provides send_text_message() and send_language_selection() for outbound
    WhatsApp messages, plus parse_language_selection() for interpreting user input.

Integration:
    send_text_message()         ← api/webhooks.py  (all outbound messages)
    send_language_selection()   ← api/webhooks.py  (language menu)
    parse_language_selection()  ← api/webhooks.py  (state machine language step)

Twilio SDK is synchronous — all send operations are wrapped in asyncio.to_thread()
to avoid blocking the event loop.
"""

import asyncio

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from twilio.rest import Client as TwilioClient

from app.core.config import settings


# ── Language catalog ──────────────────────────────────────────────────────────
# Each tuple: (whatsapp_display, session_name, code)
# Order determines the menu number (1-indexed).

SUPPORTED_LANGUAGES: list[tuple[str, str, str]] = [
    ("हिंदी (Hindi)", "Hindi", "hi"),
    ("தமிழ் (Tamil)", "Tamil", "ta"),
    ("తెలుగు (Telugu)", "Telugu", "te"),
    ("বাংলা (Bengali)", "Bengali", "bn"),
    ("ಕನ್ನಡ (Kannada)", "Kannada", "kn"),
    ("मराठी (Marathi)", "Marathi", "mr"),
    ("ગુજરાતી (Gujarati)", "Gujarati", "gu"),
    ("മലയാളം (Malayalam)", "Malayalam", "ml"),
    ("English", "English", "en"),
]


# ── Twilio singleton ──────────────────────────────────────────────────────────

_twilio_client: TwilioClient | None = None


def _get_twilio_client() -> TwilioClient:
    """Return module-level Twilio client singleton, creating it on first call."""
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = TwilioClient(
            settings.twilio_account_sid,
            settings.twilio_auth_token,
        )
    return _twilio_client


# ── Language selection ────────────────────────────────────────────────────────

def parse_language_selection(body: str) -> tuple[str, str] | None:
    """Parse a user's language selection from their WhatsApp message body.

    Accepts:
        - Position number: "1" through "9" (matches menu order)
        - Language code:   "hi", "ta", "te", "bn", "kn", "mr", "gu", "ml", "en"
        - Language name:   "Hindi", "Tamil", etc. (case-insensitive)

    Returns:
        (session_name, code) e.g. ("Hindi", "hi"), or None if unrecognized.
    """
    text = body.strip()

    # Position-based: "1" through "9"
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(SUPPORTED_LANGUAGES):
            _, session_name, code = SUPPORTED_LANGUAGES[idx]
            return session_name, code
        return None

    lower = text.lower()

    # Code-based: "hi", "ta", ...
    for _, session_name, code in SUPPORTED_LANGUAGES:
        if lower == code:
            return session_name, code

    # Name-based: "Hindi", "Tamil", ... (case-insensitive)
    for _, session_name, code in SUPPORTED_LANGUAGES:
        if lower == session_name.lower():
            return session_name, code

    return None


# ── Send functions ────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))
async def send_text_message(to: str, body: str, *, request_id: str = "") -> str:
    """Send a WhatsApp text message via Twilio.

    Twilio's Python SDK is synchronous — the blocking call is offloaded to a
    thread pool via asyncio.to_thread() so it never blocks the event loop.
    Retries 3 times with exponential backoff on transient errors.

    Args:
        to:         Recipient WhatsApp number, e.g. "whatsapp:+919876543210".
        body:       Message text (plain text or WhatsApp markdown).
        request_id: Twilio MessageSid for log correlation.

    Returns:
        Twilio message SID.
    """
    client = _get_twilio_client()
    log = logger.bind(request_id=request_id)

    def _sync_send() -> str:
        msg = client.messages.create(
            from_=settings.twilio_whatsapp_number,
            to=to,
            body=body,
        )
        return msg.sid

    sid = await asyncio.to_thread(_sync_send)
    log.info(f"WhatsApp message sent: SID={sid} to={to[:24]}")
    return sid


async def send_language_selection(to: str, *, request_id: str = "") -> str:
    """Send the numbered language selection menu to the user.

    Builds a language list with a consent notice and calls send_text_message.

    Args:
        to:         Recipient WhatsApp number.
        request_id: For log correlation.

    Returns:
        Twilio message SID from send_text_message.
    """
    lines = [
        "🏥 *SehatSamjho — Medical Document Translator*",
        "",
        "Please select your preferred language / अपनी भाषा चुनें:",
        "",
    ]
    for i, (display, _, _) in enumerate(SUPPORTED_LANGUAGES, start=1):
        lines.append(f"{i}. {display}")

    lines.extend([
        "",
        "Reply with the number (1-9) or language name.",
        "",
        "_By continuing, you consent to the processing of your medical document. "
        "No patient data is stored._",
    ])

    return await send_text_message(to, "\n".join(lines), request_id=request_id)
