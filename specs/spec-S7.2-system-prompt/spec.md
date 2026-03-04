# Spec S7.2 — System Prompt

## Overview
Build the `_build_system_prompt()` function in `translation.py` that constructs the Claude Sonnet 4.6 system prompt for medical jargon simplification and multilingual translation. The prompt establishes a caring health educator persona with strict rules: explain (don't just translate), preserve drug names and dosages in English, never add clinical advice, flag low-confidence items with a warning emoji, keep output under 300 words, and append a disclaimer. The function accepts an optional `glossary_context` block (from S6.4) that is injected into the prompt to ground translations with verified medical term mappings.

## Dependencies
- S7.1 (Anthropic client + prompt templates) — provides `_get_client()`, `CLAUDE_MODEL`, `TRANSLATION_MAX_TOKENS`, `TRANSLATION_TEMPERATURE`

## Target Location
`backend/app/services/translation.py`

---

## Functional Requirements

### FR-1: System prompt constant — `TRANSLATION_SYSTEM_PROMPT`
- **What**: A module-level string constant containing the base system prompt template. Includes a `{glossary_context}` placeholder for optional glossary injection.
- **Content rules**:
  - Persona: "You are a caring health educator helping patients understand their prescriptions."
  - Rule 1: Explain medical terms in simple, everyday language — do not just transliterate.
  - Rule 2: Always keep drug names and dosages in English (e.g., "Metformin 500mg") even when the rest is translated.
  - Rule 3: Never add clinical advice, diagnoses, or recommendations not present in the original prescription.
  - Rule 4: Flag any item where confidence is below 0.7 with a ⚠️ prefix and note it may need pharmacist verification.
  - Rule 5: Keep total output under 300 words.
  - Rule 6: End every response with a disclaimer: the translation is for understanding only and patients should consult their doctor or pharmacist for medical advice.
  - Glossary section: "Use the following verified medical term translations as grounding:\n{glossary_context}" — only present when glossary_context is non-empty.
- **Inputs**: None (it is a constant template string).
- **Outputs**: `str` — the raw template with `{glossary_context}` placeholder.

### FR-2: `_build_system_prompt(glossary_context: str = "")` function
- **What**: Builds the final system prompt string by injecting glossary context into the template.
- **Inputs**:
  - `glossary_context` (`str`, default `""`): formatted glossary block from `format_glossary_context()` (S6.4). May be empty string if no glossary matches found.
- **Outputs**: `str` — the fully rendered system prompt.
- **Behaviour**:
  - If `glossary_context` is non-empty: inject it into the glossary section of the template.
  - If `glossary_context` is empty (or whitespace-only): omit the entire glossary section from the final prompt (do not leave a blank "Use the following..." line).
- **Edge cases**:
  - `glossary_context=None` should be treated as empty string.
  - Very long glossary_context (>2000 chars) — include as-is (truncation is the caller's responsibility, handled by S6.4).

### FR-3: Prompt quality assertions (testable properties)
- **What**: The rendered system prompt must satisfy certain structural properties regardless of inputs.
- **Properties**:
  - Contains the word "health educator" (persona).
  - Contains "drug names" and "English" (drug name preservation rule).
  - Contains "300 words" (output length rule).
  - Contains "disclaimer" or "consult" (disclaimer rule).
  - Contains "⚠️" or "confidence" (low-confidence flagging rule).
  - Does NOT contain any placeholder syntax like `{glossary_context}` in the final output.
  - Does NOT contain patient data, API keys, or hardcoded secrets.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `TRANSLATION_SYSTEM_PROMPT` is a non-empty string constant exported from `translation.py`
- [ ] **Outcome 2**: `_build_system_prompt("")` returns a prompt without any glossary section
- [ ] **Outcome 3**: `_build_system_prompt(glossary_context)` returns a prompt with the glossary block injected
- [ ] **Outcome 4**: The prompt contains all 6 rules (persona, drug names, no advice, confidence flag, 300 words, disclaimer)
- [ ] **Outcome 5**: No `{glossary_context}` placeholder remains in any rendered output
- [ ] **Outcome 6**: `_build_system_prompt(None)` does not raise — treats None as empty

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

**File**: `backend/tests/services/test_system_prompt.py`

1. **test_translation_system_prompt_importable**: `TRANSLATION_SYSTEM_PROMPT` is importable from `backend.app.services.translation`
2. **test_translation_system_prompt_is_string**: `TRANSLATION_SYSTEM_PROMPT` is a `str`
3. **test_translation_system_prompt_non_empty**: `TRANSLATION_SYSTEM_PROMPT` has length > 100
4. **test_translation_system_prompt_has_placeholder**: `TRANSLATION_SYSTEM_PROMPT` contains `{glossary_context}`
5. **test_build_system_prompt_importable**: `_build_system_prompt` is importable from `backend.app.services.translation`
6. **test_build_system_prompt_callable**: `_build_system_prompt` is callable
7. **test_build_system_prompt_signature**: accepts `glossary_context` keyword argument with default `""`
8. **test_build_system_prompt_returns_string**: returns a `str`
9. **test_build_system_prompt_empty_glossary**: when called with `""`, result does not contain "Use the following" glossary header
10. **test_build_system_prompt_with_glossary**: when called with a sample glossary block, result contains the glossary text
11. **test_build_system_prompt_glossary_section_present**: when glossary provided, result contains "verified medical term translations"
12. **test_build_system_prompt_none_glossary**: `_build_system_prompt(glossary_context=None)` does not raise, omits glossary section
13. **test_build_system_prompt_whitespace_glossary**: `_build_system_prompt(glossary_context="   ")` omits glossary section
14. **test_prompt_contains_persona**: rendered prompt contains "health educator"
15. **test_prompt_contains_drug_name_rule**: rendered prompt mentions keeping drug names in English
16. **test_prompt_contains_no_advice_rule**: rendered prompt mentions not adding clinical advice
17. **test_prompt_contains_confidence_flag_rule**: rendered prompt mentions confidence and ⚠️
18. **test_prompt_contains_word_limit_rule**: rendered prompt mentions "300 words"
19. **test_prompt_contains_disclaimer_rule**: rendered prompt mentions disclaimer or consult
20. **test_prompt_no_remaining_placeholders**: no `{` or `}` template syntax in rendered output (with or without glossary)

### Mocking Strategy
- No mocking needed — `TRANSLATION_SYSTEM_PROMPT` is a constant and `_build_system_prompt()` is a pure function (no external calls, no config access).

### Coverage Expectation
- 100% line and branch coverage for `TRANSLATION_SYSTEM_PROMPT` and `_build_system_prompt()`.

---

## References
- roadmap.md Phase 7 table (S7.2 row)
- S7.1 spec (client + constants foundation)
- S6.4 spec (`format_glossary_context()` — produces the glossary_context input)
- design.md, requirements.md
