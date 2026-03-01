"""Twilio HMAC signature verification for webhook security."""

from fastapi import HTTPException, Request
from loguru import logger
from twilio.request_validator import RequestValidator

from backend.app.core.config import settings

# Module-level cached validator (lazy init via _get_request_validator)
_validator: RequestValidator | None = None


def _get_request_validator() -> RequestValidator:
    """Return a cached RequestValidator initialised with TWILIO_AUTH_TOKEN."""
    global _validator
    if _validator is None:
        _validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    return _validator


def _reconstruct_url(request: Request) -> str:
    """Reconstruct the full URL as Twilio sees it, respecting reverse-proxy headers."""
    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    forwarded_host = request.headers.get("X-Forwarded-Host")

    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}{request.url.path}"

    return str(request.url)


async def validate_twilio_signature(request: Request) -> None:
    """FastAPI dependency that validates the X-Twilio-Signature header.

    Raises HTTPException(403) if the signature is missing, empty, or invalid.
    Returns None on success (pass-through dependency).
    """
    signature = request.headers.get("X-Twilio-Signature", "")

    if not signature:
        logger.warning("Twilio signature missing or empty")
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    url = _reconstruct_url(request)
    form_data = await request.form()
    params = dict(form_data)

    validator = _get_request_validator()
    is_valid = validator.validate(url, params, signature)

    if not is_valid:
        logger.warning("Twilio signature validation failed for {url}", url=url)
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")
