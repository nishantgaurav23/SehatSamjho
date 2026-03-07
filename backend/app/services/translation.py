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
TRANSLATION_MAX_TOKENS: int = 2048
TRANSLATION_TEMPERATURE: float = 0.3

# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

TRANSLATION_SYSTEM_PROMPT: str = """\
You are a caring health educator helping patients understand their prescriptions.
Your audience is everyday people — not doctors. Write as if you are a friendly \
pharmacist explaining things face-to-face.

## Output format
Structure your response into EXACTLY these three sections using these markers:

[WHAT YOU TAKE]
Start with a one-line overview: doctor name, date, and diagnosis/ailment (if available). \
Skip any field that says "Not specified" — do not mention it at all.
Then list each medicine with its name (in English), dosage, how often to take it, \
and for how long.

[WHY THESE MEDICINES]
For EACH medicine, explain in simple words why the doctor has prescribed it. \
What does this medicine do in your body? What condition does it treat? \
If there are side effects or interactions from the Drug Information section, \
mention the most important ones briefly.

[NEXT STEPS]
Practical advice: when to take each medicine (before/after food, morning/night), \
things to avoid, warning signs to watch for, and when to see the doctor again. \
If the prescription mentions follow-up dates or tests, include them here.

## Rules
1. Explain medical terms in simple, everyday language. Do not just transliterate — \
explain what the term means (e.g. "hypertension" → "high blood pressure").
2. Always keep drug names and dosages in English even when the rest is translated.
3. Never add clinical advice, diagnoses, or recommendations not present in the \
original prescription.
4. If your confidence in any item is below 0.7, prefix it with a warning and note \
it may need pharmacist verification.
5. Keep total output under 400 words. Be concise — patients read this on a phone.
6. End with: "This translation is for understanding only. Please consult your \
doctor or pharmacist for medical advice."
7. Do NOT use markdown formatting like **, ##, or bullet points with * — use plain \
text with line breaks. The output will be sent via WhatsApp.
8. If a field is marked "Not specified", omit it entirely. Do not write "Not specified" \
in the output.
9. The section markers [WHAT YOU TAKE], [WHY THESE MEDICINES], [NEXT STEPS] must appear \
exactly as shown — they are used for parsing. Write all content in the target language \
but keep these English markers.
{glossary_context}\
"""

LAB_REPORT_SYSTEM_PROMPT: str = """\
You are a caring health educator helping patients understand their lab test reports.
Your audience is everyday people — not doctors. Write as if you are a friendly \
lab technician explaining results face-to-face.

## Output format
Structure your response into EXACTLY these three sections using these markers:

[YOUR TEST RESULTS]
Start with a one-line overview: lab/doctor name, date, and type of tests (if available). \
Skip any field that says "Not specified" — do not mention it at all.
Then list each test with its name (in English), your result value, the normal range, \
and whether your value is normal, high, or low.

[WHAT THESE RESULTS MEAN]
For EACH test that is flagged high or low, explain in simple words what it means. \
What does this test measure? Why might it be abnormal? What conditions could cause this? \
For normal results, briefly reassure the patient.

[NEXT STEPS]
Practical advice: should the patient see a doctor about any abnormal results? \
Are there any lifestyle changes that could help? Any tests that should be repeated? \
Mention any urgent values that need immediate medical attention.

## Rules
1. Explain medical terms in simple, everyday language. Do not just transliterate — \
explain what the term means (e.g. "HbA1c" → "a measure of your average blood sugar \
over the past 3 months").
2. Always keep test names, values, and units in English even when the rest is translated.
3. Never add clinical diagnoses or treatment recommendations not supported by the results.
4. If your confidence in any item is below 0.7, prefix it with a warning and note \
it may need verification.
5. Keep total output under 400 words. Be concise — patients read this on a phone.
6. End with: "This translation is for understanding only. Please consult your \
doctor for medical advice."
7. Do NOT use markdown formatting like **, ##, or bullet points with * — use plain \
text with line breaks. The output will be sent via WhatsApp.
8. If a field is marked "Not specified", omit it entirely. Do not write "Not specified" \
in the output.
9. The section markers [YOUR TEST RESULTS], [WHAT THESE RESULTS MEAN], [NEXT STEPS] must \
appear exactly as shown — they are used for parsing. Write all content in the target \
language but keep these English markers.
{glossary_context}\
"""

_GLOSSARY_HEADER: str = "\nUse the following verified medical term translations as grounding:\n"


def _build_system_prompt(glossary_context: str = "", doc_type: str = "prescription") -> str:
    """Build the final system prompt, optionally injecting glossary context.

    Args:
        glossary_context: Formatted glossary block from format_glossary_context().
            Empty string or None means no glossary section.

    Returns:
        Fully rendered system prompt string with no remaining placeholders.
    """
    template = LAB_REPORT_SYSTEM_PROMPT if doc_type == "lab_report" else TRANSLATION_SYSTEM_PROMPT
    context = glossary_context or ""
    if context.strip():
        section = _GLOSSARY_HEADER + context + "\n"
    else:
        section = ""
    return template.replace("{glossary_context}", section)


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
) -> str:
    """Build the user-turn prompt for the Claude translation call.

    Pure function — no I/O, no side effects, no logging.
    Glossary context is injected via the system prompt only (not duplicated here).

    Args:
        prescription: Structured extraction output from GPT-4O Vision.
        language_name: Target language display name (e.g. "Hindi").
        language_code: Target language BCP-47 code (e.g. "hi").
        drug_info_list: Optional enrichment data per medicine from drug lookup.

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
            if drug is None:
                continue
            parts.append(f"### {drug.brand_name}")
            parts.append(f"- Generic Name: {drug.generic_name or 'Unknown'}")
            parts.append(f"- Therapeutic Class: {drug.therapeutic_class or 'Unknown'}")
            parts.append(f"- Purpose: {drug.purpose_en or 'Unknown'}")
            parts.append(f"- Side Effects: {drug.side_effects_en or 'Unknown'}")
            parts.append(f"- Timing: {drug.timing_instructions or 'Unknown'}")
            parts.append(f"- Known Interactions: {drug.known_interactions or 'None known'}")

    return "\n".join(parts)


def _build_lab_report_user_prompt(
    prescription: PrescriptionData,
    language_name: str,
    language_code: str,
) -> str:
    """Build the user-turn prompt for a lab report translation call."""
    parts: list[str] = []

    parts.append(f"Translate the following lab report into {language_name} ({language_code}).")

    parts.append("")
    parts.append("## Report Details")
    parts.append(f"Lab/Doctor: {prescription.doctor_name or _NOT_SPECIFIED}")
    parts.append(f"Date: {prescription.date or _NOT_SPECIFIED}")
    parts.append(f"Diagnosis: {prescription.diagnosis or _NOT_SPECIFIED}")
    parts.append(f"Overall Confidence: {prescription.overall_confidence}")

    for idx, test in enumerate(prescription.lab_tests, start=1):
        marker = "[LOW CONFIDENCE] " if test.confidence < _LOW_CONFIDENCE_THRESHOLD else ""
        parts.append("")
        parts.append(f"### {marker}Test {idx}: {test.test_name}")
        parts.append(f"- Value: {test.value or _NOT_SPECIFIED}")
        parts.append(f"- Unit: {test.unit or _NOT_SPECIFIED}")
        parts.append(f"- Reference Range: {test.reference_range or _NOT_SPECIFIED}")
        parts.append(f"- Flag: {test.flag or _NOT_SPECIFIED}")
        parts.append(f"- Confidence: {test.confidence}")

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

    First tries the explicit English pattern (Disclaimer:/Note:).
    If not found, uses the last paragraph as the disclaimer — this handles
    translated responses where Claude writes the disclaimer in Hindi, Tamil, etc.
    Falls back to ``_DEFAULT_DISCLAIMER`` only if the text has a single paragraph.
    """
    # Try explicit English pattern first
    match = _DISCLAIMER_PATTERN.search(text)
    if match:
        disclaimer = match.group(1).strip().lstrip("*").strip()
        for prefix in ("Disclaimer:", "disclaimer:", "Note:", "note:"):
            if disclaimer.startswith(prefix):
                disclaimer = disclaimer[len(prefix) :].strip()
                break
        body = text[: match.start()].strip()
        return body, disclaimer

    # Fallback: use last paragraph (split on double newline)
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    if len(paragraphs) >= 2:
        last = paragraphs[-1].lstrip("*").strip()
        # A heading (###) is medicine content, not a disclaimer — skip it
        if not last.startswith("#"):
            body = "\n\n".join(paragraphs[:-1])
            return body, last

    return text.strip(), _DEFAULT_DISCLAIMER


_SECTION_MARKERS_RX = ["[WHAT YOU TAKE]", "[WHY THESE MEDICINES]", "[NEXT STEPS]"]
_SECTION_MARKERS_LAB = ["[YOUR TEST RESULTS]", "[WHAT THESE RESULTS MEAN]", "[NEXT STEPS]"]
_SECTION_KEYS = ["medicines", "why", "next_steps"]


def _extract_sections(text: str, doc_type: str = "prescription") -> dict[str, str]:
    """Extract the 3 structured sections from the translation output.

    Returns a dict with keys: 'medicines', 'why', 'next_steps'.
    Values are the text content of each section (empty string if not found).
    """
    markers = _SECTION_MARKERS_LAB if doc_type == "lab_report" else _SECTION_MARKERS_RX
    sections = {k: "" for k in _SECTION_KEYS}

    positions = []
    for marker in markers:
        pos = text.find(marker)
        positions.append(pos)

    for i, (pos, key) in enumerate(zip(positions, _SECTION_KEYS)):
        if pos == -1:
            continue
        start = pos + len(markers[i])
        next_positions = [p for p in positions[i + 1 :] if p > pos]
        end = min(next_positions) if next_positions else len(text)
        sections[key] = text[start:end].strip()

    return sections


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
    doc_type: str = "prescription",
) -> TranslationResult:
    """Call Claude Sonnet 4.6 to simplify and translate a prescription or lab report.

    Builds system + user prompts, calls the Anthropic Messages API,
    parses the response into a ``TranslationResult``.

    Retries up to 3 times on transient Anthropic API errors (timeout,
    connection, rate limit, internal server). Non-retryable errors
    (authentication, bad request) propagate immediately.
    """
    # FR-2: Build prompts
    system_prompt = _build_system_prompt(glossary_context, doc_type=doc_type)
    if doc_type == "lab_report":
        user_prompt = _build_lab_report_user_prompt(
            prescription,
            language_name,
            language_code,
        )
    else:
        user_prompt = _build_user_prompt(
            prescription,
            language_name,
            language_code,
            drug_info_list,
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
