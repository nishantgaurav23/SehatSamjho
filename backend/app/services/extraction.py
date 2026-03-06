"""GPT-4O Vision extraction service — prescription image → structured data.

Uses OpenAI GPT-4O Vision to extract structured medical data from
prescription images. This module provides the async client singleton,
the extraction prompt constants, the prompt builder, and the public
``extract_prescription()`` orchestration function.
"""

from __future__ import annotations

import base64
import json
import re
from typing import TYPE_CHECKING

import httpx
import openai
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from backend.app.models.schemas import PrescriptionData


# ---------------------------------------------------------------------------
# Custom exception classes (S5.5)
# ---------------------------------------------------------------------------


class ExtractionError(Exception):
    """Base class for all extraction-related errors."""


class NotMedicalDocumentError(ExtractionError):
    """Raised when the document is not a medical document (doc_type == 'other')."""


class ImageNotReadableError(ExtractionError):
    """Raised when the image cannot be processed or is too unclear."""


# ---------------------------------------------------------------------------
# Module-level client cache (singleton, lazy-initialised)
# ---------------------------------------------------------------------------

_client: openai.AsyncOpenAI | None = None

# ---------------------------------------------------------------------------
# Extraction prompt constants (S5.2)
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT: str = (
    "You are a medical document reader specializing in Indian prescriptions.\n\n"
    "Your task is to extract structured data from the provided prescription image "
    "and return it as valid JSON.\n\n"
    "Rules:\n"
    "1. Return ONLY valid JSON — no markdown fences, no code fences, no commentary.\n"
    "2. Assign a `confidence` score (0.0–1.0) per medicine entry based on how clearly "
    "the fields are readable.\n"
    "3. Assign an `overall_confidence` score (0.0–1.0) for the entire document.\n"
    "4. If a dosage, frequency, or duration is unclear, do not guess — set `confidence` "
    "below 0.5 and leave the field as `null`.\n"
    '5. Set `doc_type` to `"prescription"`, `"lab_report"`, or `"other"` based on '
    "the document content.\n"
    "6. Do not invent patient details. If a field is not present in the image, "
    "set it to `null`.\n"
)

EXTRACTION_OUTPUT_SCHEMA: str = (
    "Expected JSON output schema:\n"
    "{\n"
    '  "doctor_name": str | null,\n'
    '  "patient_name": str | null,\n'
    '  "date": str | null,\n'
    '  "diagnosis": str | null,\n'
    '  "medicines": [\n'
    "    {\n"
    '      "medicine_name": str (required),\n'
    '      "dosage": str | null,\n'
    '      "frequency": str | null,\n'
    '      "duration": str | null,\n'
    '      "instructions": str | null,\n'
    '      "confidence": float (0.0–1.0)\n'
    "    }\n"
    "  ],\n"
    '  "overall_confidence": float (0.0–1.0),\n'
    '  "doc_type": str ("prescription" | "lab_report" | "other")\n'
    "}\n"
)


def _build_extraction_prompt() -> list[dict[str, str]]:
    """Build the complete prompt messages list for the GPT-4O Vision API call.

    Returns a list containing a single system message dict that combines
    EXTRACTION_SYSTEM_PROMPT and EXTRACTION_OUTPUT_SCHEMA.
    This function is pure — no I/O, no settings access, fully deterministic.
    """
    combined = EXTRACTION_SYSTEM_PROMPT + "\n" + EXTRACTION_OUTPUT_SCHEMA
    return [{"role": "system", "content": combined}]


def _get_client() -> openai.AsyncOpenAI:
    """Return a cached ``AsyncOpenAI`` client, creating it on first call.

    Settings are imported lazily inside this function (not at module level)
    to avoid import-time side effects in tests that don't set env vars.
    """
    global _client
    if _client is None:
        from backend.app.core.config import settings

        logger.debug("Creating OpenAI AsyncOpenAI client")
        _client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _client


def _reset_client() -> None:
    """Clear the cached client so the next ``_get_client()`` creates a fresh one."""
    global _client
    _client = None


# ---------------------------------------------------------------------------
# GPT-4O Vision constants (S5.3)
# ---------------------------------------------------------------------------

GPT4O_MODEL: str = "gpt-4o"
GPT4O_MAX_TOKENS: int = 1024
GPT4O_TEMPERATURE: float = 0.1
GPT4O_IMAGE_DETAIL: str = "high"


# ---------------------------------------------------------------------------
# Image helpers (S5.3)
# ---------------------------------------------------------------------------


def _encode_image_base64(image_bytes: bytes, content_type: str = "image/jpeg") -> str:
    """Base64-encode raw image bytes into a data URI string.

    Pure function — no I/O, no side effects.
    """
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"


async def _download_image(image_url: str) -> bytes:
    """Download an image from a URL using httpx.

    Returns raw image bytes. Raises ``httpx.HTTPStatusError`` on non-2xx
    and ``httpx.TimeoutException`` on timeout (both propagated to caller).
    """
    logger.debug("Downloading image from URL")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(image_url)
        response.raise_for_status()
        logger.debug("Image download complete")
        return response.content


# ---------------------------------------------------------------------------
# GPT-4O Vision call (S5.3)
# ---------------------------------------------------------------------------


def _log_retry(retry_state) -> None:
    """Log a warning before each tenacity retry sleep."""
    logger.warning(
        "Retrying _call_gpt4o_vision: attempt={}, wait={:.1f}s, error={}",
        retry_state.attempt_number,
        retry_state.next_action.sleep if retry_state.next_action else 0,
        repr(retry_state.outcome.exception()) if retry_state.outcome else "unknown",
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.InternalServerError,
        )
    ),
    reraise=True,
    before_sleep=_log_retry,
)
async def _call_gpt4o_vision(image_url: str, content_type: str = "image/jpeg") -> str:
    """Orchestrate the GPT-4O Vision API call for prescription extraction.

    Downloads the image, base64-encodes it, builds the message payload
    with the extraction system prompt, and calls OpenAI. Returns the raw
    JSON string from the model response.
    """
    image_bytes = await _download_image(image_url)
    data_uri = _encode_image_base64(image_bytes, content_type)

    system_messages = _build_extraction_prompt()
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": data_uri, "detail": GPT4O_IMAGE_DETAIL},
            },
            {
                "type": "text",
                "text": "Extract all medical information from this prescription image.",
            },
        ],
    }

    client = _get_client()
    logger.debug("Calling GPT-4O Vision model={}", GPT4O_MODEL)
    response = await client.chat.completions.create(
        model=GPT4O_MODEL,
        messages=system_messages + [user_message],
        max_tokens=GPT4O_MAX_TOKENS,
        temperature=GPT4O_TEMPERATURE,
    )

    if not response.choices:
        raise ValueError("GPT-4O returned no choices")

    logger.debug(
        "GPT-4O response: prompt_tokens={}, completion_tokens={}",
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )

    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Public API — extract_prescription (S5.4)
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.InternalServerError,
        )
    ),
    reraise=True,
    before_sleep=_log_retry,
)
async def _call_gpt4o_vision_from_bytes(
    image_bytes: bytes, content_type: str = "image/jpeg"
) -> str:
    """Call GPT-4O Vision with raw image bytes (no download needed).

    Used by the web upload endpoint where the image is already in memory.
    """
    data_uri = _encode_image_base64(image_bytes, content_type)

    system_messages = _build_extraction_prompt()
    user_message = {
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": data_uri, "detail": GPT4O_IMAGE_DETAIL},
            },
            {
                "type": "text",
                "text": "Extract all medical information from this prescription image.",
            },
        ],
    }

    client = _get_client()
    logger.debug("Calling GPT-4O Vision (from bytes) model={}", GPT4O_MODEL)
    response = await client.chat.completions.create(
        model=GPT4O_MODEL,
        messages=system_messages + [user_message],
        max_tokens=GPT4O_MAX_TOKENS,
        temperature=GPT4O_TEMPERATURE,
    )

    if not response.choices:
        raise ValueError("GPT-4O returned no choices")

    return response.choices[0].message.content or ""


_CODE_FENCE_RE = re.compile(r"^```(?:\w*)\n(.*)\n```$", re.DOTALL)


async def extract_prescription_from_bytes(
    image_bytes: bytes,
    content_type: str = "image/jpeg",
    request_id: str | None = None,
) -> "PrescriptionData":
    """Extract structured prescription data from raw image bytes.

    Same pipeline as extract_prescription() but skips the URL download step.
    Used by the web upload endpoint.
    """
    from backend.app.models.schemas import PrescriptionData

    log = logger.bind(request_id=request_id) if request_id else logger

    if not image_bytes:
        raise ValueError("image_bytes must be non-empty")

    log.info("Starting prescription extraction from bytes")

    raw_json = await _call_gpt4o_vision_from_bytes(image_bytes, content_type)

    stripped = raw_json.strip()
    fence_match = _CODE_FENCE_RE.match(stripped)
    if fence_match:
        stripped = fence_match.group(1)

    if not stripped:
        log.error("GPT-4O returned empty response")
        raise ValueError("GPT-4O returned an empty response")

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        log.error("Failed to parse GPT-4O response as JSON: {}", str(exc))
        raise ValueError(f"Invalid JSON from GPT-4O: {exc}") from exc

    try:
        result = PrescriptionData.model_validate(data)
    except Exception as exc:
        log.error("PrescriptionData validation failed: {}", str(exc))
        raise ValueError(f"Prescription validation error: {exc}") from exc

    if result.doc_type == "other":
        log.warning("Document is not a medical document: doc_type={}", result.doc_type)
        raise NotMedicalDocumentError(
            f"Document is not a medical document (doc_type={result.doc_type})"
        )

    if result.overall_confidence < 0.3:
        log.warning("Image too unclear: overall_confidence={}", result.overall_confidence)
        raise ImageNotReadableError(
            f"Image too unclear to extract reliably "
            f"(overall_confidence={result.overall_confidence})"
        )

    log.info(
        "Extraction from bytes complete: doc_type={}, medicines={}",
        result.doc_type,
        len(result.medicines),
    )
    return result


async def extract_prescription(
    image_url: str,
    content_type: str = "image/jpeg",
    request_id: str | None = None,
) -> "PrescriptionData":
    """Extract structured prescription data from an image URL.

    Orchestrates: validate URL → call GPT-4O Vision → parse JSON →
    validate as ``PrescriptionData`` → semantic checks → return.

    This is the single public entry point consumed by Phase 10 pipeline.
    """
    from backend.app.models.schemas import PrescriptionData

    # Bind request_id to log context when available
    log = logger.bind(request_id=request_id) if request_id else logger

    # FR-2: validate image URL
    if not image_url or not image_url.strip():
        raise ValueError("image_url must be a non-empty string")

    log.info("Starting prescription extraction")

    # FR-3: call GPT-4O Vision (with httpx error wrapping)
    try:
        raw_json = await _call_gpt4o_vision(image_url, content_type)
    except httpx.HTTPStatusError as exc:
        log.error("Image download failed: HTTP {}", exc.response.status_code)
        raise ImageNotReadableError(
            f"Image download failed: HTTP {exc.response.status_code}"
        ) from exc
    except httpx.TimeoutException as exc:
        log.error("Image download timed out")
        raise ImageNotReadableError("Image download timed out") from exc

    # FR-4: strip code fences if present, then parse JSON
    stripped = raw_json.strip()
    fence_match = _CODE_FENCE_RE.match(stripped)
    if fence_match:
        stripped = fence_match.group(1)

    if not stripped:
        log.error("GPT-4O returned empty response")
        raise ValueError("GPT-4O returned an empty response")

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        log.error("Failed to parse GPT-4O response as JSON: {}", str(exc))
        raise ValueError(f"Invalid JSON from GPT-4O: {exc}") from exc

    # FR-5: validate as PrescriptionData
    try:
        result = PrescriptionData.model_validate(data)
    except Exception as exc:
        log.error("PrescriptionData validation failed: {}", str(exc))
        raise ValueError(f"Prescription validation error: {exc}") from exc

    # S5.5 FR-2: Semantic error detection
    if result.doc_type == "other":
        log.warning("Document is not a medical document: doc_type={}", result.doc_type)
        raise NotMedicalDocumentError(
            f"Document is not a medical document (doc_type={result.doc_type})"
        )

    if result.overall_confidence < 0.3:
        log.warning("Image too unclear: overall_confidence={}", result.overall_confidence)
        raise ImageNotReadableError(
            f"Image too unclear to extract reliably "
            f"(overall_confidence={result.overall_confidence})"
        )

    log.info(
        "Extraction complete: doc_type={}, medicines={}",
        result.doc_type,
        len(result.medicines),
    )
    return result
