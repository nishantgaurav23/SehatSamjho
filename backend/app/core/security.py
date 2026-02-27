"""
Authentication and request-verification utilities for SehatSamjho.

Provides:
    verify_twilio_signature() — validate webhook POST came from Twilio (HMAC-SHA1)
    hash_phone()              — one-way SHA-256 hash of a phone number

Integration:
    verify_twilio_signature ← api/webhooks.py  (validates every incoming POST)
    hash_phone              ← api/webhooks.py  (before writing phone to DB)

Twilio signature verification:
    In production (validate_twilio_signature=True) every request without a valid
    X-Twilio-Signature header is rejected with 403.
    In development (validate_twilio_signature=False) the check is skipped so
    local curl/ngrok testing works without signing every request.
"""

import hashlib

from loguru import logger
from twilio.request_validator import RequestValidator

from app.core.config import settings


def verify_twilio_signature(url: str, params: dict[str, str], signature: str) -> bool:
    """Verify the HMAC-SHA1 signature Twilio attaches to every webhook POST.

    Args:
        url:       Full public URL of the endpoint (must match exactly what
                   Twilio sees, including https:// and any query string).
        params:    POST form fields as a plain dict (str → str).
        signature: Value of the X-Twilio-Signature request header.

    Returns:
        True  — signature is valid, or validation is disabled (development).
        False — signature mismatch (log warning; caller should return 403).
    """
    if not settings.validate_twilio_signature:
        return True

    validator = RequestValidator(settings.twilio_auth_token)
    is_valid = validator.validate(url, params, signature)

    if not is_valid:
        logger.warning("Twilio signature verification failed — possible spoofed request")

    return is_valid


def hash_phone(phone: str) -> str:
    """Return a deterministic, one-way SHA-256 hash of a phone number.

    The same phone always produces the same hash, so we can count unique
    users in analytics without storing the actual number (zero PHI).

    Args:
        phone: Raw Twilio From string, e.g. "whatsapp:+919876543210".

    Returns:
        64-character lowercase hex digest.
    """
    return hashlib.sha256(phone.encode()).hexdigest()
