"""Bhashini TTS API client — converts text to speech via Bhashini pipeline inference.

Also provides S3 upload for audio delivery (S9.3).
"""

from __future__ import annotations

import base64
import time
from asyncio import to_thread as asyncio_to_thread
from uuid import uuid4

import boto3
import httpx
from botocore.exceptions import ClientError
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BHASHINI_INFERENCE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
BHASHINI_TTS_GENDER = "female"
MAX_AUDIO_SIZE = 10 * 1024 * 1024  # 10 MB
AUDIO_UNAVAILABLE_MESSAGE = "Audio is not available at the moment. Please read the text below."

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class BhashiniTTSError(Exception):
    """Raised on any Bhashini TTS failure (HTTP error, empty audio, timeout, etc.)."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ---------------------------------------------------------------------------
# Lazy singleton httpx.AsyncClient
# ---------------------------------------------------------------------------

_httpx_client: httpx.AsyncClient | None = None


def _get_httpx_client() -> httpx.AsyncClient:
    """Return a reusable httpx.AsyncClient (lazy-initialized singleton)."""
    global _httpx_client
    if _httpx_client is None:
        _httpx_client = httpx.AsyncClient(timeout=30.0)
    return _httpx_client


def _reset_httpx_client() -> None:
    """Clear the httpx client singleton (for testing)."""
    global _httpx_client
    _httpx_client = None


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------


def _build_bhashini_payload(text: str, language_code: str) -> dict:
    """Construct the JSON payload for Bhashini pipeline inference TTS."""
    return {
        "pipelineTasks": [
            {
                "taskType": "tts",
                "config": {
                    "language": {"sourceLanguage": language_code},
                    "gender": BHASHINI_TTS_GENDER,
                },
            }
        ],
        "inputData": {"input": [{"source": text}]},
    }


# ---------------------------------------------------------------------------
# Core API call
# ---------------------------------------------------------------------------


async def _call_bhashini(
    text: str,
    language_code: str,
    request_id: str = "",
) -> bytes:
    """POST to Bhashini TTS and return decoded audio bytes.

    Raises BhashiniTTSError on any failure.
    """
    from backend.app.core.config import settings

    logger.info(
        "Bhashini TTS request | request_id={} | language={} | text_length={}",
        request_id,
        language_code,
        len(text),
    )

    payload = _build_bhashini_payload(text, language_code)
    headers = {
        "Authorization": settings.BHASHINI_API_KEY,
        "Content-Type": "application/json",
        "userID": settings.BHASHINI_USER_ID,
    }

    client = _get_httpx_client()
    start = time.monotonic()

    try:
        response = await client.post(
            BHASHINI_INFERENCE_URL,
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        logger.error(
            "Bhashini TTS timeout | request_id={} | error={}",
            request_id,
            type(exc).__name__,
        )
        raise BhashiniTTSError("Bhashini TTS request timed out") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.error(
            "Bhashini TTS HTTP error | request_id={} | status={}",
            request_id,
            status,
        )
        raise BhashiniTTSError(f"Bhashini TTS HTTP error: {status}", status_code=status) from exc

    # Parse response JSON
    try:
        data = response.json()
    except (ValueError, TypeError) as exc:
        logger.error("Bhashini TTS malformed JSON | request_id={}", request_id)
        raise BhashiniTTSError("Bhashini TTS returned malformed JSON") from exc

    # Extract audio content
    try:
        audio_b64 = data["pipelineResponse"][0]["output"][0]["audio"][0]["audioContent"]
    except (KeyError, IndexError, TypeError) as exc:
        logger.error("Bhashini TTS missing audio key | request_id={}", request_id)
        raise BhashiniTTSError("Bhashini TTS response missing audio content") from exc

    if not audio_b64:
        logger.error("Bhashini TTS empty audio | request_id={}", request_id)
        raise BhashiniTTSError("Bhashini TTS returned empty audio content")

    audio_bytes = base64.b64decode(audio_b64)
    elapsed_ms = (time.monotonic() - start) * 1000

    logger.info(
        "Bhashini TTS success | request_id={} | audio_bytes={} | latency_ms={:.0f}",
        request_id,
        len(audio_bytes),
        elapsed_ms,
    )

    return audio_bytes


# ---------------------------------------------------------------------------
# Public API — text_to_speech()
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception_type(BhashiniTTSError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def text_to_speech(
    text: str,
    language_code: str,
    request_id: str = "",
) -> bytes:
    """Convert translated text to speech audio bytes via Bhashini TTS.

    Validates inputs, calls _call_bhashini(), validates audio size,
    and retries on transient BhashiniTTSError (up to 3 attempts).

    Raises ValueError on invalid inputs (not retried).
    Raises BhashiniTTSError on Bhashini failures or invalid audio.
    """
    if not text or not text.strip():
        raise ValueError("text must be a non-empty string")
    if not language_code:
        raise ValueError("language_code must be a non-empty string")

    logger.info(
        "text_to_speech start | request_id={} | language={} | text_length={}",
        request_id,
        language_code,
        len(text),
    )

    audio_bytes = await _call_bhashini(text, language_code, request_id=request_id)

    if not audio_bytes:
        raise BhashiniTTSError("text_to_speech received empty audio from Bhashini")

    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise BhashiniTTSError(
            f"Audio size {len(audio_bytes)} exceeds MAX_AUDIO_SIZE ({MAX_AUDIO_SIZE})"
        )

    logger.info(
        "text_to_speech success | request_id={} | audio_bytes={}",
        request_id,
        len(audio_bytes),
    )

    return audio_bytes


# ---------------------------------------------------------------------------
# S3 Upload (S9.3)
# ---------------------------------------------------------------------------


class S3UploadError(Exception):
    """Raised on any S3 upload failure."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# ---------------------------------------------------------------------------
# Lazy S3 client singleton
# ---------------------------------------------------------------------------

_s3_client = None


def _get_s3_client():
    """Return a reusable boto3 S3 client (lazy-initialized singleton)."""
    global _s3_client
    if _s3_client is None:
        from backend.app.core.config import settings

        from botocore.config import Config

        kwargs = {
            "service_name": "s3",
            "region_name": "ap-south-1",
            "config": Config(signature_version="s3v4"),
        }
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        _s3_client = boto3.client(**kwargs)
    return _s3_client


def _reset_s3_client() -> None:
    """Clear the S3 client singleton (for testing)."""
    global _s3_client
    _s3_client = None


# ---------------------------------------------------------------------------
# _upload_to_s3
# ---------------------------------------------------------------------------


async def _upload_to_s3(
    audio_bytes: bytes,
    request_id: str = "",
    extension: str = ".ogg",
    content_type: str = "audio/ogg",
) -> str:
    """Upload audio bytes to S3 and return a presigned URL.

    Raises ValueError on empty audio_bytes.
    Raises S3UploadError on S3 failures.
    """
    if not audio_bytes:
        raise ValueError("audio_bytes must be non-empty")

    s3 = _get_s3_client()
    from backend.app.core.config import settings

    key = f"audio/{uuid4()}{extension}"

    logger.info(
        "S3 upload start | request_id={} | key={} | size={}",
        request_id,
        key,
        len(audio_bytes),
    )

    try:
        await asyncio_to_thread(
            lambda: s3.put_object(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=audio_bytes,
                ContentType=content_type,
            )
        )
    except (ClientError, Exception) as exc:
        logger.error(
            "S3 upload failed | request_id={} | key={} | error={}",
            request_id,
            key,
            type(exc).__name__,
        )
        raise S3UploadError(f"S3 put_object failed: {exc}") from exc

    try:
        presigned_url = await asyncio_to_thread(
            lambda: s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BUCKET, "Key": key},
                ExpiresIn=3600,
            )
        )
    except (ClientError, Exception) as exc:
        logger.error(
            "S3 presigned URL failed | request_id={} | key={} | error={}",
            request_id,
            key,
            type(exc).__name__,
        )
        raise S3UploadError(f"S3 generate_presigned_url failed: {exc}") from exc

    logger.info(
        "S3 upload success | request_id={} | key={} | url_length={}",
        request_id,
        key,
        len(presigned_url),
    )

    return presigned_url


# ---------------------------------------------------------------------------
# S9.4 — Audio Delivery Orchestrator
# ---------------------------------------------------------------------------


async def _get_audio_bytes(
    text: str,
    language_code: str,
    request_id: str = "",
) -> tuple[bytes, str] | tuple[None, None]:
    """Try Bhashini first (if API key set), then Edge TTS fallback.

    Returns (audio_bytes, content_type) or (None, None) if both fail.
    """
    from backend.app.core.config import settings

    # Try Bhashini first if API key is configured
    bhashini_key = getattr(settings, "BHASHINI_API_KEY", "")
    if bhashini_key and bhashini_key.strip():
        try:
            audio_bytes = await text_to_speech(text, language_code, request_id=request_id)
            logger.info(
                "Bhashini TTS used | request_id={} | audio_bytes={}",
                request_id,
                len(audio_bytes),
            )
            return audio_bytes, "audio/ogg"
        except BhashiniTTSError as exc:
            logger.warning(
                "Bhashini TTS failed, trying Edge TTS | request_id={} | error={}",
                request_id,
                exc,
            )
    else:
        logger.info(
            "Bhashini API key not set, using Edge TTS | request_id={}",
            request_id,
        )

    # Fallback to Edge TTS
    try:
        from backend.app.services.tts_edge import edge_text_to_speech

        audio_bytes = await edge_text_to_speech(text, language_code, request_id=request_id)
        logger.info(
            "Edge TTS used | request_id={} | audio_bytes={}",
            request_id,
            len(audio_bytes),
        )
        return audio_bytes, "audio/mp3"
    except Exception as exc:
        logger.warning(
            "Edge TTS also failed | request_id={} | error_type={} | error={}",
            request_id,
            type(exc).__name__,
            exc,
        )
        return None, None


async def generate_and_deliver_audio(
    text: str,
    language_code: str,
    request_id: str = "",
) -> str | None:
    """Orchestrate TTS + S3 upload and return a presigned URL.

    Tries Bhashini first (if API key set), then Edge TTS fallback.
    Uploads audio to S3 and returns a presigned URL.

    Raises ValueError on empty text/language_code (before any downstream call).
    Returns None on total TTS failure or S3UploadError (graceful degradation).
    """
    if not text or not text.strip():
        raise ValueError("text must be a non-empty string")
    if not language_code:
        raise ValueError("language_code must be a non-empty string")

    logger.info(
        "generate_and_deliver_audio start | request_id={} | language={} | text_length={}",
        request_id,
        language_code,
        len(text),
    )

    start = time.monotonic()

    audio_bytes, content_type = await _get_audio_bytes(text, language_code, request_id)
    if audio_bytes is None:
        logger.warning(
            "generate_and_deliver_audio degraded (all TTS failed) | request_id={}",
            request_id,
        )
        return None

    ext = ".mp3" if content_type == "audio/mp3" else ".ogg"

    try:
        presigned_url = await _upload_to_s3(
            audio_bytes, request_id=request_id, extension=ext, content_type=content_type
        )
    except S3UploadError as exc:
        logger.warning(
            "generate_and_deliver_audio degraded (S3) | request_id={} | error_type={} | error={}",
            request_id,
            type(exc).__name__,
            exc,
        )
        return None

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        "generate_and_deliver_audio done | request_id={} | url_length={} | latency_ms={:.0f}",
        request_id,
        len(presigned_url),
        elapsed_ms,
    )

    return presigned_url
