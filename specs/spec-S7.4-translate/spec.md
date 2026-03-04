# Spec S7.4 — simplify_and_translate()

## Overview
Public orchestrator function that calls the Anthropic Claude Sonnet 4.6 API via `client.messages.create()` with the system prompt (S7.2) and user prompt (S7.3), then parses the response into a `TranslationResult` Pydantic model containing `translated_text`, `per_medicine_summaries`, `disclaimer`, and `language_code`. This is the public API consumed by the Phase 10 pipeline.

## Dependencies
- **S7.2** — `_build_system_prompt()` (system prompt builder)
- **S7.3** — `_build_user_prompt()` (user prompt builder)
- **S5.5** — Error taxonomy (extraction errors pattern — reused pattern for translation errors)

## Target Location
`backend/app/services/translation.py`

---

## Functional Requirements

### FR-1: Function signature and async
- **What**: `simplify_and_translate()` is an `async def` function.
- **Inputs**:
  - `prescription: PrescriptionData` — structured extraction output
  - `language_name: str` — target language display name (e.g. "Hindi")
  - `language_code: str` — target language BCP-47 code (e.g. "hi")
  - `drug_info_list: list[DrugInfo] | None = None` — optional drug enrichment
  - `glossary_context: str = ""` — optional formatted glossary block
  - `request_id: str = ""` — for log correlation
- **Outputs**: `TranslationResult`
- **Edge cases**: All optional params default to empty/None

### FR-2: Build prompts
- **What**: Calls `_build_system_prompt(glossary_context)` and `_build_user_prompt(prescription, language_name, language_code, drug_info_list, glossary_context)` to construct the Claude API call inputs.
- **Inputs**: Function parameters passed through
- **Outputs**: Two strings (system_prompt, user_prompt)

### FR-3: Call Claude API
- **What**: Calls `_get_client().messages.create()` with:
  - `model=CLAUDE_MODEL` ("claude-sonnet-4-6")
  - `max_tokens=TRANSLATION_MAX_TOKENS` (1024)
  - `temperature=TRANSLATION_TEMPERATURE` (0.3)
  - `system=system_prompt`
  - `messages=[{"role": "user", "content": user_prompt}]`
- **Inputs**: Built system and user prompts
- **Outputs**: `anthropic.types.Message` response object
- **Edge cases**: API errors propagated (retry handled in S7.5)

### FR-4: Parse response text
- **What**: Extract the text content from `response.content[0].text`. Handle the case where `response.content` is empty or the first block is not a `TextBlock`.
- **Inputs**: Claude API response
- **Outputs**: Raw response text string
- **Edge cases**: Empty content list, non-text content block

### FR-5: Parse into TranslationResult
- **What**: Parse the Claude response text into a `TranslationResult` model. The response is expected to be structured text (not JSON). Extract:
  - `translated_text`: The full translated response text
  - `per_medicine_summaries`: Extract individual medicine summary lines (lines starting with medicine names or numbered items within the response)
  - `disclaimer`: The disclaimer paragraph at the end of the response (Claude is instructed to always include one)
  - `language_code`: Pass through from input
- **Inputs**: Raw response text, language_code
- **Outputs**: `TranslationResult` instance
- **Edge cases**: Missing disclaimer (use a default), no medicine summaries (empty list), very short response

### FR-6: Logging
- **What**: Log at appropriate levels with `request_id`:
  - `logger.info` on successful translation (include language_code, response length)
  - `logger.warning` if disclaimer extraction falls back to default
  - `logger.error` on parse failures
- **Inputs**: request_id, language_code, response data
- **Edge cases**: Never log translated text content (may contain prescription details from prompt)

### FR-7: PHI-safe logging
- **What**: Never log the actual translated text, prescription content, or patient information. Only log metadata: language_code, response length, token usage if available, latency.
- **Inputs**: All log calls
- **Outputs**: Log entries with no PHI

---

## Tangible Outcomes

- [ ] **Outcome 1**: `simplify_and_translate` is importable from `backend.app.services.translation`
- [ ] **Outcome 2**: Function is `async def` and accepts the specified signature
- [ ] **Outcome 3**: Calls `client.messages.create()` with correct model, max_tokens, temperature, system, messages
- [ ] **Outcome 4**: Returns a valid `TranslationResult` with all fields populated
- [ ] **Outcome 5**: Extracts per-medicine summaries from response text
- [ ] **Outcome 6**: Extracts or provides default disclaimer
- [ ] **Outcome 7**: Logs success/failure with request_id, never logs PHI
- [ ] **Outcome 8**: Handles empty/malformed API responses gracefully

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

**Import & Signature (3 tests)**
1. **test_import_simplify_and_translate**: Function importable from module
2. **test_is_async**: Function is a coroutine function
3. **test_signature_params**: Accepts prescription, language_name, language_code, drug_info_list, glossary_context, request_id

**Happy Path (5 tests)**
4. **test_happy_path_returns_translation_result**: Mock Claude API, verify TranslationResult returned
5. **test_calls_messages_create_with_correct_params**: Verify model, max_tokens, temperature, system, messages
6. **test_passes_glossary_to_system_prompt**: Glossary context included in system prompt
7. **test_passes_drug_info_to_user_prompt**: Drug info list included in user prompt
8. **test_language_code_in_result**: language_code passed through to TranslationResult

**Response Parsing (5 tests)**
9. **test_extracts_translated_text**: Full response text captured
10. **test_extracts_disclaimer_from_response**: Disclaimer extracted from end of response
11. **test_default_disclaimer_when_missing**: Fallback disclaimer when not in response
12. **test_extracts_per_medicine_summaries**: Medicine summaries parsed from response
13. **test_empty_medicines_yields_empty_summaries**: No medicines = empty summaries list

**Edge Cases (4 tests)**
14. **test_empty_response_content**: Handles empty content list
15. **test_no_drug_info**: Works with drug_info_list=None
16. **test_no_glossary_context**: Works with glossary_context=""
17. **test_minimal_prescription**: Works with prescription having no optional fields

**Logging (3 tests)**
18. **test_logs_success_with_request_id**: Info log on success includes request_id
19. **test_logs_response_length**: Info log includes response length
20. **test_never_logs_translated_text**: Translated content not in log output

### Mocking Strategy
- `_get_client()` — mock to return a mock `AsyncAnthropic` client
- `client.messages.create()` — `AsyncMock` returning a mock `Message` with `content=[TextBlock(text=...)]`
- All logging — capture with `loguru` sink or mock `logger`
- No real API calls in tests

### Coverage Expectation
- All public functions have at least one test; edge cases covered
- 20 tests total
