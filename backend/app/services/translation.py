"""Claude Sonnet 4.6 translation service — medical jargon simplification + multilingual translation.

Uses Anthropic Claude Sonnet 4.6 to simplify medical jargon and translate into the
patient's chosen language. This module provides the async client singleton, model
constants, prompt builders (S7.2–S7.3), the public orchestrator
``simplify_and_translate()`` (S7.4), and retry / error handling (S7.5).
"""

from __future__ import annotations

import re

import anthropic
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.app.models.schemas import DrugInfo, PrescriptionData, TranslationResult


# ---------------------------------------------------------------------------
# Custom exception classes (S7.5)
# ---------------------------------------------------------------------------


class TranslationError(Exception):
    """Base class for all translation-related errors."""


# ---------------------------------------------------------------------------
# Module-level client cache (singleton, lazy-initialised)
# ---------------------------------------------------------------------------

_client: anthropic.AsyncAnthropic | None = None

# ---------------------------------------------------------------------------
# Model and API call constants
# ---------------------------------------------------------------------------

CLAUDE_MODEL: str = "claude-sonnet-4-6"
TRANSLATION_MAX_TOKENS: int = 1024
TRANSLATION_TEMPERATURE: float = 0.3

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

TRANSLATION_SYSTEM_PROMPT: str = """\
You are a caring health educator helping patients understand their prescriptions.

Rules:
1. Explain medical terms in simple, everyday language. Do not just transliterate.
2. Always keep drug names and dosages in English (e.g., "Metformin 500mg") even when \
the rest is translated.
3. Never add clinical advice, diagnoses, or recommendations not present in the \
original prescription.
4. If your confidence in any item is below 0.7, prefix it with \u26a0\ufe0f and note \
it may need pharmacist verification.
5. Keep total output under 300 words.
6. End every response with a disclaimer: the translation is for understanding only \
and patients should consult their doctor or pharmacist for medical advice.
{glossary_context}\
"""

_GLOSSARY_HEADER: str = "\nUse the following verified medical term translations as grounding:\n"


def _build_system_prompt(glossary_context: str = "") -> str:
    """Build the final system prompt, optionally injecting glossary context.

    Args:
        glossary_context: Formatted glossary block from format_glossary_context().
            Empty string or None means no glossary section.

    Returns:
        Fully rendered system prompt string with no remaining placeholders.
    """
    context = glossary_context or ""
    if context.strip():
        section = _GLOSSARY_HEADER + context + "\n"
    else:
        section = ""
    return TRANSLATION_SYSTEM_PROMPT.replace("{glossary_context}", section)


# ---------------------------------------------------------------------------
# Client management
# ---------------------------------------------------------------------------


def _get_client() -> anthropic.AsyncAnthropic:
    """Return a cached ``AsyncAnthropic`` client, creating it on first call.

    Settings are imported lazily inside this function (not at module level)
    to avoid import-time side effects in tests that don't set env vars.
    """
    global _client
    if _client is None:
        from backend.app.core.config import settings

        logger.debug("Creating Anthropic AsyncAnthropic client")
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _reset_client() -> None:
    """Clear the cached client so the next ``_get_client()`` creates a fresh one."""
    global _client
    _client = None


# ---------------------------------------------------------------------------
# User prompt builder (S7.3)
# ---------------------------------------------------------------------------

_NOT_SPECIFIED: str = "Not specified"
_LOW_CONFIDENCE_THRESHOLD: float = 0.7


def _build_user_prompt(
    prescription: PrescriptionData,
    language_name: str,
    language_code: str,
    drug_info_list: list[DrugInfo] | None = None,
    glossary_context: str = "",
) -> str:
    """Build the user-turn prompt for the Claude translation call.

    Pure function — no I/O, no side effects, no logging.

    Args:
        prescription: Structured extraction output from GPT-4O Vision.
        language_name: Target language display name (e.g. "Hindi").
        language_code: Target language BCP-47 code (e.g. "hi").
        drug_info_list: Optional enrichment data per medicine from drug lookup.
        glossary_context: Optional pre-formatted glossary block.

    Returns:
        Fully rendered user prompt string.
    """
    parts: list[str] = []

    # FR-2: Language target header
    parts.append(f"Translate the following prescription into {language_name} ({language_code}).")

    # FR-3: Prescription metadata (FR-7: patient_name excluded)
    parts.append("")
    parts.append("## Prescription Details")
    parts.append(f"Doctor: {prescription.doctor_name or _NOT_SPECIFIED}")
    parts.append(f"Date: {prescription.date or _NOT_SPECIFIED}")
    parts.append(f"Diagnosis: {prescription.diagnosis or _NOT_SPECIFIED}")
    parts.append(f"Overall Confidence: {prescription.overall_confidence}")

    # FR-4: Medicine entries
    for idx, med in enumerate(prescription.medicines, start=1):
        marker = "[LOW CONFIDENCE] " if med.confidence < _LOW_CONFIDENCE_THRESHOLD else ""
        parts.append("")
        parts.append(f"### {marker}Medicine {idx}: {med.medicine_name}")
        parts.append(f"- Dosage: {med.dosage or _NOT_SPECIFIED}")
        parts.append(f"- Frequency: {med.frequency or _NOT_SPECIFIED}")
        parts.append(f"- Duration: {med.duration or _NOT_SPECIFIED}")
        parts.append(f"- Instructions: {med.instructions or _NOT_SPECIFIED}")
        parts.append(f"- Confidence: {med.confidence}")

    # FR-5: Drug enrichment section
    if drug_info_list:
        parts.append("")
        parts.append("## Drug Information")
        for drug in drug_info_list:
            parts.append(f"### {drug.brand_name}")
            parts.append(f"- Generic Name: {drug.generic_name or 'Unknown'}")
            parts.append(f"- Therapeutic Class: {drug.therapeutic_class or 'Unknown'}")
            parts.append(f"- Purpose: {drug.purpose_en or 'Unknown'}")
            parts.append(f"- Side Effects: {drug.side_effects_en or 'Unknown'}")
            parts.append(f"- Timing: {drug.timing_instructions or 'Unknown'}")
            parts.append(f"- Known Interactions: {drug.known_interactions or 'None known'}")

    # FR-6: Glossary context section
    if glossary_context and glossary_context.strip():
        parts.append("")
        parts.append("## Glossary Reference")
        parts.append(glossary_context)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Default disclaimer (fallback when Claude omits one)
# ---------------------------------------------------------------------------

_DEFAULT_DISCLAIMER: str = (
    "This translation is for understanding only. "
    "Please consult your doctor or pharmacist for medical advice."
)

# Pattern to detect a disclaimer paragraph (case-insensitive)
_DISCLAIMER_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|\n\n)(\**(?:disclaimer|note)\**[:\s].+)",
    re.IGNORECASE | re.DOTALL,
)

# Pattern to detect per-medicine summary headings (### Medicine or ### DrugName)
_MEDICINE_HEADING_RE: re.Pattern[str] = re.compile(
    r"^#{1,4}\s+(.+)$",
    re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Response parser (internal)
# ---------------------------------------------------------------------------


def _extract_disclaimer(text: str) -> tuple[str, str]:
    """Split response text into (body, disclaimer).

    Returns the disclaimer paragraph and the body with disclaimer removed.
    Falls back to ``_DEFAULT_DISCLAIMER`` if none found.
    """
    match = _DISCLAIMER_PATTERN.search(text)
    if match:
        disclaimer = match.group(1).strip().lstrip("*").strip()
        # Remove leading "Disclaimer:" / "Note:" prefix
        for prefix in ("Disclaimer:", "disclaimer:", "Note:", "note:"):
            if disclaimer.startswith(prefix):
                disclaimer = disclaimer[len(prefix) :].strip()
                break
        body = text[: match.start()].strip()
        return body, disclaimer
    return text.strip(), _DEFAULT_DISCLAIMER


def _extract_medicine_summaries(text: str) -> list[str]:
    """Extract per-medicine summary sections from the response body.

    Looks for markdown headings (### MedicineName) and collects the text
    beneath each heading until the next heading or end of text.
    """
    headings = list(_MEDICINE_HEADING_RE.finditer(text))
    if not headings:
        return []

    summaries: list[str] = []
    for i, m in enumerate(headings):
        title = m.group(1).strip()
        # Skip non-medicine headings
        lower = title.lower()
        if lower.startswith("your") or lower.startswith("prescription"):
            continue
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[start:end].strip()
        summary = f"{title}: {body}" if body else title
        summaries.append(summary)
    return summaries


# ---------------------------------------------------------------------------
# Retry logging callback (S7.5)
# ---------------------------------------------------------------------------


def _log_translation_retry(retry_state) -> None:
    """Log each retry attempt — PHI-safe (no prompt/response content)."""
    logger.warning(
        "Retrying simplify_and_translate: attempt={}, wait={:.1f}s, error={}",
        retry_state.attempt_number,
        retry_state.next_action.sleep if retry_state.next_action else 0,
        repr(retry_state.outcome.exception()) if retry_state.outcome else "unknown",
    )


# ---------------------------------------------------------------------------
# Public orchestrator (S7.4) + retry (S7.5)
# ---------------------------------------------------------------------------


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (
            anthropic.APITimeoutError,
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        )
    ),
    reraise=True,
    before_sleep=_log_translation_retry,
)
async def simplify_and_translate(
    prescription: PrescriptionData,
    language_name: str,
    language_code: str,
    drug_info_list: list[DrugInfo] | None = None,
    glossary_context: str = "",
    request_id: str = "",
) -> TranslationResult:
    """Call Claude Sonnet 4.6 to simplify and translate a prescription.

    Builds system + user prompts, calls the Anthropic Messages API,
    parses the response into a ``TranslationResult``.

    Retries up to 3 times on transient Anthropic API errors (timeout,
    connection, rate limit, internal server). Non-retryable errors
    (authentication, bad request) propagate immediately.

    Args:
        prescription: Structured extraction output from GPT-4O Vision.
        language_name: Target language display name (e.g. "Hindi").
        language_code: Target language BCP-47 code (e.g. "hi").
        drug_info_list: Optional enrichment data per medicine.
        glossary_context: Optional formatted glossary block.
        request_id: Correlation ID for logging.

    Returns:
        ``TranslationResult`` with translated_text, per_medicine_summaries,
        disclaimer, and language_code.

    Raises:
        TranslationError: If the Claude API returns an empty or whitespace-only response.
    """
    # FR-2: Build prompts
    system_prompt = _build_system_prompt(glossary_context)
    user_prompt = _build_user_prompt(
        prescription,
        language_name,
        language_code,
        drug_info_list,
        glossary_context,
    )

    # FR-3: Call Claude API
    client = _get_client()
    logger.debug("Calling Claude API | request_id={}", request_id)

    response = await client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=TRANSLATION_MAX_TOKENS,
        temperature=TRANSLATION_TEMPERATURE,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    # FR-4: Extract text from response
    if not response.content:
        logger.error(
            "Empty response from Claude API | request_id={} language={}",
            request_id,
            language_code,
        )
        raise TranslationError("Empty response from Claude API")

    raw_text = response.content[0].text

    if not raw_text or not raw_text.strip():
        logger.error(
            "Empty/whitespace-only response from Claude API | request_id={} language={}",
            request_id,
            language_code,
        )
        raise TranslationError("Empty whitespace-only response from Claude API")

    # FR-5: Parse into TranslationResult
    body, disclaimer = _extract_disclaimer(raw_text)
    if disclaimer == _DEFAULT_DISCLAIMER:
        logger.warning(
            "Disclaimer not found in response, using default | request_id={}",
            request_id,
        )

    summaries = _extract_medicine_summaries(body)

    result = TranslationResult(
        translated_text=raw_text,
        per_medicine_summaries=summaries,
        disclaimer=disclaimer,
        language_code=language_code,
    )

    # FR-6/7: PHI-safe success log (no translated text content)
    logger.info(
        "Translation complete | request_id={} language={} response_len={} summaries={}",
        request_id,
        language_code,
        len(raw_text),
        len(summaries),
    )

    return result
