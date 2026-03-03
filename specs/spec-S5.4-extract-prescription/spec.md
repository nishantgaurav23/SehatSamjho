# Spec S5.4 — extract prescription

## Overview

Public orchestration function `extract_prescription()` that ties together the entire GPT-4O Vision extraction pipeline. Validates the incoming image URL, calls `_call_gpt4o_vision()` (S5.3) to get raw JSON, parses the JSON string, validates it as a `PrescriptionData` Pydantic model (S2.4), and returns the typed result. This is the single public API surface for extraction, consumed by the Phase 10 pipeline wiring (S10.1).

## Dependencies

- **S5.3** — `_call_gpt4o_vision()` (download + GPT-4O call + raw JSON response)
- **S2.4** — `PrescriptionData` Pydantic model (structured validation)

## Target Location

`backend/app/services/extraction.py` (append to existing module)

---

## Functional Requirements

### FR-1: `extract_prescription()` signature

- **What**: Async function `extract_prescription(image_url: str, content_type: str = "image/jpeg") -> PrescriptionData`
- **Inputs**: `image_url` (str, Twilio MediaUrl), `content_type` (str, default `"image/jpeg"`)
- **Outputs**: Validated `PrescriptionData` instance
- **Edge cases**: Empty string URL, non-string URL

### FR-2: Image URL validation

- **What**: Before calling GPT-4O, validate that `image_url` is a non-empty string. Raise `ValueError` with a clear message if blank/empty.
- **Inputs**: `image_url` parameter
- **Outputs**: Pass-through if valid; `ValueError` if invalid
- **Edge cases**: Empty string `""`, whitespace-only `"   "`

### FR-3: Call GPT-4O Vision

- **What**: Delegate to `_call_gpt4o_vision(image_url, content_type)` to get the raw JSON string response from GPT-4O.
- **Inputs**: Validated `image_url` and `content_type`
- **Outputs**: Raw JSON string from GPT-4O
- **Edge cases**: Empty string response from GPT-4O (should raise)

### FR-4: Parse JSON response

- **What**: Parse the raw JSON string returned by GPT-4O into a Python dict using `json.loads()`. Handle JSON wrapped in markdown code fences (```json ... ```) by stripping them before parsing. Raise `ValueError` if parsing fails.
- **Inputs**: Raw JSON string from GPT-4O
- **Outputs**: Python dict
- **Edge cases**: Invalid JSON, JSON wrapped in code fences, empty string

### FR-5: Validate as PrescriptionData

- **What**: Construct a `PrescriptionData` instance from the parsed dict using `PrescriptionData(**data)` or `PrescriptionData.model_validate(data)`. Raise `ValueError` if Pydantic validation fails (wrapping the `ValidationError`).
- **Inputs**: Parsed dict from FR-4
- **Outputs**: `PrescriptionData` instance
- **Edge cases**: Missing required fields (overall_confidence), confidence out of range, medicines with empty name

### FR-6: Logging

- **What**: Log key milestones at `info` level: start of extraction (no PHI — do not log the image URL), successful completion with doc_type and medicine count. Log errors at `error` level with context but no PHI.
- **Inputs**: Extraction lifecycle events
- **Outputs**: Loguru log entries
- **Edge cases**: Ensure image URLs are never logged (PHI-adjacent — Twilio URLs contain phone numbers)

### FR-7: Return validated result

- **What**: Return the validated `PrescriptionData` to the caller. This is the public API for Phase 10 pipeline.
- **Inputs**: Validated `PrescriptionData`
- **Outputs**: `PrescriptionData`

---

## Tangible Outcomes

- [ ] **Outcome 1**: `extract_prescription()` is an async function importable from `backend.app.services.extraction`
- [ ] **Outcome 2**: Given a valid image URL and mocked GPT-4O returning valid JSON, returns a `PrescriptionData` instance with correct fields
- [ ] **Outcome 3**: Given an empty/blank image URL, raises `ValueError` before calling GPT-4O
- [ ] **Outcome 4**: Given GPT-4O returning invalid JSON, raises `ValueError` with descriptive message
- [ ] **Outcome 5**: Given GPT-4O returning JSON wrapped in markdown code fences, strips fences and parses correctly
- [ ] **Outcome 6**: Given GPT-4O returning valid JSON that fails PrescriptionData validation, raises `ValueError`
- [ ] **Outcome 7**: Given GPT-4O returning an empty string, raises `ValueError`
- [ ] **Outcome 8**: Logs extraction start and completion at info level (no PHI)
- [ ] **Outcome 9**: Does not log image URLs anywhere
- [ ] **Outcome 10**: `extract_prescription` is listed in the module's public API

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

**File**: `backend/tests/services/test_extract_prescription.py`

1. **test_extract_prescription_importable**: `extract_prescription` is importable from `backend.app.services.extraction`
2. **test_extract_prescription_is_async**: Function is a coroutine function
3. **test_extract_prescription_signature**: Accepts `image_url` (str) and `content_type` (str, default "image/jpeg"), returns `PrescriptionData`
4. **test_extract_prescription_happy_path**: Mock `_call_gpt4o_vision` to return valid JSON; assert returns `PrescriptionData` with correct fields
5. **test_extract_prescription_happy_path_medicines**: Assert returned `PrescriptionData.medicines` has correct count and fields
6. **test_extract_prescription_passes_content_type**: Verify `content_type` param is forwarded to `_call_gpt4o_vision`
7. **test_extract_prescription_empty_url_raises**: `extract_prescription("")` raises `ValueError`
8. **test_extract_prescription_whitespace_url_raises**: `extract_prescription("   ")` raises `ValueError`
9. **test_extract_prescription_invalid_json_raises**: Mock GPT-4O returning `"not json"` — raises `ValueError`
10. **test_extract_prescription_empty_response_raises**: Mock GPT-4O returning `""` — raises `ValueError`
11. **test_extract_prescription_strips_code_fences**: Mock GPT-4O returning `` ```json\n{...}\n``` `` — parses correctly
12. **test_extract_prescription_strips_code_fences_no_lang**: Mock GPT-4O returning `` ```\n{...}\n``` `` — parses correctly
13. **test_extract_prescription_validation_error**: Mock GPT-4O returning JSON with `confidence: 2.0` (out of range) — raises `ValueError`
14. **test_extract_prescription_missing_required_field**: Mock GPT-4O returning JSON without `overall_confidence` — raises `ValueError`
15. **test_extract_prescription_logs_start**: Assert loguru `info` called at extraction start (no image URL in message)
16. **test_extract_prescription_logs_completion**: Assert loguru `info` called with doc_type and medicine count on success
17. **test_extract_prescription_logs_error_on_invalid_json**: Assert loguru `error` called when JSON parsing fails
18. **test_extract_prescription_no_phi_in_logs**: Assert image URL never appears in any log call arguments
19. **test_extract_prescription_calls_gpt4o_vision**: Assert `_call_gpt4o_vision` is called exactly once with correct args
20. **test_extract_prescription_propagates_gpt4o_errors**: If `_call_gpt4o_vision` raises (e.g., `httpx.HTTPStatusError`), it propagates to caller

### Mocking Strategy

- **`_call_gpt4o_vision`**: Patch at `backend.app.services.extraction._call_gpt4o_vision` — returns raw JSON string
- **`loguru.logger`**: Patch at `backend.app.services.extraction.logger` to inspect log calls
- **No real OpenAI / network calls** — all mocked

### Coverage Expectation

- All public functions have at least one test
- Happy path, edge cases (empty URL, bad JSON, code fences, validation failures), and error propagation covered
- PHI-safety assertions in log tests

---

## References

- roadmap.md — S5.4 row
- `backend/app/services/extraction.py` — existing S5.1/S5.2/S5.3 code
- `backend/app/models/schemas.py` — `PrescriptionData`, `MedicineEntry`
