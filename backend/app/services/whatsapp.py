"""WhatsApp service — language constants, helpers, and Twilio messaging.

Single source of truth for supported languages across the application.
Used by language selection, TTS, translation, and glossary modules.
Provides async Twilio WhatsApp messaging with retry and PHI-safe logging.
"""

from __future__ import annotations

import asyncio
import hashlib
from urllib.parse import urlparse

from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

# ---------------------------------------------------------------------------
# FR-1: SUPPORTED_LANGUAGES — all 22 scheduled Indian languages
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: dict[str, dict[str, str]] = {
    "en": {"name": "English", "display_name": "English", "bhashini_code": "en"},
    "hi": {"name": "Hindi", "display_name": "हिन्दी", "bhashini_code": "hi"},
    "bn": {"name": "Bengali", "display_name": "বাংলা", "bhashini_code": "bn"},
    "ta": {"name": "Tamil", "display_name": "தமிழ்", "bhashini_code": "ta"},
    "te": {"name": "Telugu", "display_name": "తెలుగు", "bhashini_code": "te"},
    "mr": {"name": "Marathi", "display_name": "मराठी", "bhashini_code": "mr"},
    "gu": {"name": "Gujarati", "display_name": "ગુજરાતી", "bhashini_code": "gu"},
    "kn": {"name": "Kannada", "display_name": "ಕನ್ನಡ", "bhashini_code": "kn"},
    "ml": {"name": "Malayalam", "display_name": "മലയാളം", "bhashini_code": "ml"},
    "or": {"name": "Odia", "display_name": "ଓଡ଼ିଆ", "bhashini_code": "or"},
    "pa": {"name": "Punjabi", "display_name": "ਪੰਜਾਬੀ", "bhashini_code": "pa"},
    "as": {"name": "Assamese", "display_name": "অসমীয়া", "bhashini_code": "as"},
    "ur": {"name": "Urdu", "display_name": "اردو", "bhashini_code": "ur"},
    "ks": {"name": "Kashmiri", "display_name": "كٲشُر", "bhashini_code": "ks"},
    "sd": {"name": "Sindhi", "display_name": "سنڌي", "bhashini_code": "sd"},
    "kok": {"name": "Konkani", "display_name": "कोंकणी", "bhashini_code": "kok"},
    "mai": {"name": "Maithili", "display_name": "मैथिली", "bhashini_code": "mai"},
    "doi": {"name": "Dogri", "display_name": "डोगरी", "bhashini_code": "doi"},
    "mni": {"name": "Manipuri", "display_name": "মণিপুরী", "bhashini_code": "mni"},
    "sat": {"name": "Santali", "display_name": "ᱥᱟᱱᱛᱟᱲᱤ", "bhashini_code": "sat"},
    "ne": {"name": "Nepali", "display_name": "नेपाली", "bhashini_code": "ne"},
    "brx": {"name": "Bodo", "display_name": "बड़ो", "bhashini_code": "brx"},
    "sa": {"name": "Sanskrit", "display_name": "संस्कृतम्", "bhashini_code": "sa"},
}

# ---------------------------------------------------------------------------
# FR-2: TOP_LANGUAGES — top 8 by user population
# ---------------------------------------------------------------------------

TOP_LANGUAGES: list[str] = ["hi", "bn", "ta", "te", "mr", "gu", "kn", "ml"]

# ---------------------------------------------------------------------------
# FR-3: get_language_name()
# ---------------------------------------------------------------------------


def get_language_name(code: str) -> str | None:
    """Return the English name for a valid language code, or None if not found.

    Case-insensitive. Empty string returns None.
    """
    if not code:
        return None
    entry = SUPPORTED_LANGUAGES.get(code.lower())
    return entry["name"] if entry else None


# ---------------------------------------------------------------------------
# FR-4: is_supported_language()
# ---------------------------------------------------------------------------


def is_supported_language(code: str) -> bool:
    """Return True if the code is in SUPPORTED_LANGUAGES.

    Case-insensitive. Empty string returns False.
    """
    if not code:
        return False
    return code.lower() in SUPPORTED_LANGUAGES


# ---------------------------------------------------------------------------
# FR-5: parse_language_selection()
# ---------------------------------------------------------------------------

# Pre-build reverse lookup dicts for O(1) matching
_NAME_TO_CODE: dict[str, str] = {
    entry["name"].lower(): code for code, entry in SUPPORTED_LANGUAGES.items()
}
_DISPLAY_TO_CODE: dict[str, str] = {
    entry["display_name"]: code for code, entry in SUPPORTED_LANGUAGES.items()
}


def parse_language_selection(user_input: str) -> tuple[str, str] | None:
    """Parse user input into a (language_name, language_code) tuple.

    Accepts: a number 1–8 (TOP_LANGUAGES index), a language code (e.g. "hi"),
    or a language name (English or native display_name). Case-insensitive.

    Returns None if the input is not recognised.

    Priority: language code > numeric selection > English name > display_name.
    """
    stripped = user_input.strip()
    if not stripped:
        return None

    # --- Try language code match first (highest priority) ---
    lowered = stripped.lower()
    if lowered in SUPPORTED_LANGUAGES:
        return (SUPPORTED_LANGUAGES[lowered]["name"], lowered)

    # --- Try numeric match (1–8 → TOP_LANGUAGES) ---
    if stripped.isdigit():
        idx = int(stripped)
        if 1 <= idx <= len(TOP_LANGUAGES):
            code = TOP_LANGUAGES[idx - 1]
            return (SUPPORTED_LANGUAGES[code]["name"], code)
        return None

    # --- Try English name match (case-insensitive) ---
    if lowered in _NAME_TO_CODE:
        code = _NAME_TO_CODE[lowered]
        return (SUPPORTED_LANGUAGES[code]["name"], code)

    # --- Try native display_name match (exact) ---
    if stripped in _DISPLAY_TO_CODE:
        code = _DISPLAY_TO_CODE[stripped]
        return (SUPPORTED_LANGUAGES[code]["name"], code)

    return None


# ---------------------------------------------------------------------------
# S3.3 FR-1: Twilio Client — lazy singleton
# ---------------------------------------------------------------------------

_twilio_client: Client | None = None


def _get_twilio_client() -> Client:
    """Return a lazy-initialized Twilio REST client singleton.

    Uses settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN.
    Client is created on first call, not at import time.
    """
    from backend.app.core.config import settings

    global _twilio_client
    if _twilio_client is None:
        _twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    return _twilio_client


# ---------------------------------------------------------------------------
# S3.3 FR-2 + FR-3 + FR-4: send_text_message with retry and logging
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(TwilioRestException),
    reraise=True,
)
async def send_text_message(to: str, body: str) -> str:
    """Send a WhatsApp text message via Twilio.

    Args:
        to: Recipient in WhatsApp format (e.g. "whatsapp:+919876543210").
        body: Message text (max 1600 chars per WhatsApp limit).

    Returns:
        The Twilio message SID string on success.

    Raises:
        ValueError: If ``to`` or ``body`` is empty/whitespace.
        TwilioRestException: After 3 retry attempts are exhausted.
    """
    if not to or not to.strip():
        raise ValueError("Recipient cannot be empty")
    if not body or not body.strip():
        raise ValueError("Message body cannot be empty")

    from backend.app.core.config import settings

    to_hash = hashlib.sha256(to.encode()).hexdigest()[:12]
    logger.info("Sending WhatsApp text", to_hash=to_hash, body_length=len(body))

    client = _get_twilio_client()

    try:
        msg = await asyncio.to_thread(
            client.messages.create,
            from_=settings.TWILIO_WHATSAPP_FROM,
            to=to,
            body=body,
        )
    except TwilioRestException as e:
        logger.error("WhatsApp text send failed", error=str(e))
        raise

    logger.info("WhatsApp text sent", message_sid=msg.sid)
    return msg.sid


# ---------------------------------------------------------------------------
# S3.4 FR-1: build_language_menu_text()
# ---------------------------------------------------------------------------


def build_language_menu_text() -> str:
    """Build a numbered text list of the top 8 languages plus a 'More' option.

    Returns a string with 9 lines (1-indexed), matching parse_language_selection()
    numeric input for positions 1-8.
    """
    lines: list[str] = []
    for i, code in enumerate(TOP_LANGUAGES):
        lang = SUPPORTED_LANGUAGES[code]
        lines.append(f"{i + 1}. {lang['name']} ({lang['display_name']})")
    lines.append("9. More languages")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# S3.4 FR-2: send_language_selection()
# ---------------------------------------------------------------------------


async def send_language_selection(to: str) -> str:
    """Send the language selection menu to a WhatsApp user.

    Attempts Twilio Content Templates (ContentSid) if TWILIO_CONTENT_SID is set,
    otherwise falls back to a plain text numbered list via send_text_message().

    Args:
        to: Recipient in WhatsApp format (e.g. "whatsapp:+919876543210").

    Returns:
        The Twilio message SID string on success.

    Raises:
        ValueError: If ``to`` is empty/whitespace.
    """
    if not to or not to.strip():
        raise ValueError("Recipient cannot be empty")

    from backend.app.core.config import settings

    to_hash = hashlib.sha256(to.encode()).hexdigest()[:12]
    logger.info("Sending language selection", to_hash=to_hash)

    # Try ContentSid path if configured
    content_sid = getattr(settings, "TWILIO_CONTENT_SID", None)
    if content_sid:
        try:
            client = _get_twilio_client()
            msg = await asyncio.to_thread(
                client.messages.create,
                from_=settings.TWILIO_WHATSAPP_FROM,
                to=to,
                content_sid=content_sid,
            )
            logger.info("Language selection sent via ContentSid", message_sid=msg.sid)
            return msg.sid
        except TwilioRestException as e:
            logger.warning("ContentSid failed, falling back to text", error=str(e))

    # Fallback: plain text numbered list
    menu_text = build_language_menu_text()
    sid = await send_text_message(to=to, body=menu_text)
    logger.info("Language selection sent via text", message_sid=sid)
    return sid


# ---------------------------------------------------------------------------
# S3.4 FR-3: send_more_languages()
# ---------------------------------------------------------------------------


async def send_more_languages(to: str) -> str:
    """Send the remaining 14 languages (all minus top 8) as a text list.

    Each line uses language code (not number): "code: Name (display_name)".
    Languages sorted alphabetically by English name.

    Args:
        to: Recipient in WhatsApp format (e.g. "whatsapp:+919876543210").

    Returns:
        The Twilio message SID string on success.

    Raises:
        ValueError: If ``to`` is empty/whitespace.
    """
    if not to or not to.strip():
        raise ValueError("Recipient cannot be empty")

    to_hash = hashlib.sha256(to.encode()).hexdigest()[:12]
    logger.info("Sending more languages", to_hash=to_hash)

    top_set = set(TOP_LANGUAGES)
    remaining = [(code, lang) for code, lang in SUPPORTED_LANGUAGES.items() if code not in top_set]
    remaining.sort(key=lambda item: item[1]["name"])

    lines: list[str] = []
    for code, lang in remaining:
        lines.append(f"{code}: {lang['name']} ({lang['display_name']})")

    body = "\n".join(lines)
    sid = await send_text_message(to=to, body=body)
    logger.info("More languages sent", message_sid=sid)
    return sid


# ---------------------------------------------------------------------------
# S3.5 FR-1 + FR-2: send_audio_message with retry and PHI-safe logging
# ---------------------------------------------------------------------------

_DEFAULT_AUDIO_CAPTION = "Audio summary of your prescription"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(TwilioRestException),
    reraise=True,
)
async def send_audio_message(to: str, media_url: str, caption: str | None = None) -> str:
    """Send a WhatsApp media message containing an audio file via Twilio.

    Args:
        to: Recipient in WhatsApp format (e.g. "whatsapp:+919876543210").
        media_url: Publicly accessible URL to the audio file (S3 presigned URL).
        caption: Optional text caption sent alongside the audio.

    Returns:
        The Twilio message SID string on success.

    Raises:
        ValueError: If ``to`` or ``media_url`` is empty/whitespace.
        TwilioRestException: After 3 retry attempts are exhausted.
    """
    if not to or not to.strip():
        raise ValueError("Recipient cannot be empty")
    if not media_url or not media_url.strip():
        raise ValueError("Media URL cannot be empty")

    from backend.app.core.config import settings

    to_hash = hashlib.sha256(to.encode()).hexdigest()[:12]
    media_domain = urlparse(media_url).netloc
    body = caption if caption is not None else _DEFAULT_AUDIO_CAPTION

    logger.info(
        "Sending WhatsApp audio",
        to_hash=to_hash,
        media_url_domain=media_domain,
        caption_length=len(body),
    )

    client = _get_twilio_client()

    try:
        msg = await asyncio.to_thread(
            client.messages.create,
            from_=settings.TWILIO_WHATSAPP_FROM,
            to=to,
            body=body,
            media_url=[media_url],
        )
    except TwilioRestException as e:
        logger.error("WhatsApp audio send failed", error=str(e))
        raise

    logger.info("WhatsApp audio sent", message_sid=msg.sid)
    return msg.sid


# ---------------------------------------------------------------------------
# S3.5 FR-3: send_audio_message_with_fallback
# ---------------------------------------------------------------------------


async def send_audio_message_with_fallback(
    to: str,
    media_url: str,
    fallback_text: str,
    caption: str | None = None,
) -> tuple[str, bool]:
    """Attempt audio delivery, falling back to text-only if media send fails.

    Args:
        to: Recipient in WhatsApp format.
        media_url: Audio file URL.
        fallback_text: Text to send if audio delivery fails.
        caption: Optional caption for the audio message.

    Returns:
        Tuple of (message_sid, audio_sent) where audio_sent is True if media
        was delivered, False if fallback was used.

    Raises:
        TwilioRestException: If both audio and text fallback fail.
    """
    try:
        sid = await send_audio_message(to, media_url, caption)
        return (sid, True)
    except Exception:
        to_hash = hashlib.sha256(to.encode()).hexdigest()[:12]
        logger.warning("Audio send failed, falling back to text", to_hash=to_hash)
        sid = await send_text_message(to, fallback_text)
        return (sid, False)
