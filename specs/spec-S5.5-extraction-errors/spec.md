# Spec S5.5 — Error Taxonomy + Retry

## Overview
Adds custom exception classes for semantic extraction failures and tenacity-based retry logic for transient OpenAI API errors. `NotMedicalDocumentError` and `ImageNotReadableError` represent deterministic failures that should not be retried. Transient OpenAI errors (rate limits, server errors, timeouts) are retried with exponential backoff. All failures are logged with `request_id` for traceability.

## Dependencies
- S5.4 (`extract_prescription()` — the orchestration function that will raise these exceptions and use retry)

## Target Location
- `backend/app/services/extraction.py`

---

## Functional Requirements

### FR-1: Custom exception classes
- **What**: Define `ExtractionError` (base), `NotMedicalDocumentError`, and `ImageNotReadableError` as module-level exception classes in `extraction.py`.
- **Details**:
  - `ExtractionError(Exception)` — base class for all extraction-related errors.
  - `NotMedicalDocumentError(ExtractionError)` — raised when `doc_type == "other"` or overall_confidence is too low to be a medical document. Not retried.
  - `ImageNotReadableError(ExtractionError)` — raised when the image cannot be processed (download failure, corrupt data, unreadable content with very low overall_confidence). Not retried.
- **Inputs**: Error message string.
- **Outputs**: Exception instances with descriptive messages.
- **Edge cases**: Each exception must be importable from `backend.app.services.extraction`.

### FR-2: Semantic error detection in `extract_prescription()`
- **What**: After GPT-4O returns and `PrescriptionData` is validated, check for semantic error conditions and raise the appropriate custom exception.
- **Rules**:
  - If `doc_type == "other"` → raise `NotMedicalDocumentError`.
  - If `overall_confidence < 0.3` → raise `ImageNotReadableError` (the image was too unclear to extract reliably).
- **Inputs**: Validated `PrescriptionData` object.
- **Outputs**: Raises exception or returns normally.
- **Edge cases**: `doc_type == "prescription"` or `"lab_report"` with low confidence should NOT raise `NotMedicalDocumentError` — only the confidence check applies.

### FR-3: Tenacity retry on `_call_gpt4o_vision()`
- **What**: Wrap `_call_gpt4o_vision()` with `@retry` from tenacity for transient OpenAI errors.
- **Config**:
  - `stop=stop_after_attempt(3)` — max 3 attempts.
  - `wait=wait_exponential(multiplier=1, min=2, max=10)` — exponential backoff: 2s, 4s, 8s (capped at 10s).
  - `retry=retry_if_exception_type((openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError))` — only transient errors.
  - `reraise=True` — re-raise the last exception if all attempts fail.
  - `before_sleep` — log each retry attempt with attempt number and wait time.
- **Inputs**: Same as existing `_call_gpt4o_vision()`.
- **Outputs**: Same as existing; retries are transparent to the caller.
- **Edge cases**: Non-transient errors (e.g., `openai.AuthenticationError`, `openai.BadRequestError`) must NOT be retried — they should propagate immediately.

### FR-4: Wrap image download errors
- **What**: Convert `httpx.HTTPStatusError` and `httpx.TimeoutException` from `_download_image()` into `ImageNotReadableError` inside `extract_prescription()`.
- **Inputs**: `httpx` exceptions raised during image download.
- **Outputs**: `ImageNotReadableError` with descriptive message.
- **Edge cases**: The original exception is chained (`raise ... from exc`).

### FR-5: Logging with request_id
- **What**: All error log messages in extraction must include `request_id` context when available. The `extract_prescription()` function accepts an optional `request_id: str | None = None` parameter and binds it to log context.
- **Inputs**: `request_id` string (UUID) or `None`.
- **Outputs**: Log entries include `request_id` field.
- **Edge cases**: If `request_id` is `None`, logs should still work (just without the request_id field).

---

## Tangible Outcomes

- [ ] **Outcome 1**: `ExtractionError`, `NotMedicalDocumentError`, `ImageNotReadableError` are importable from `backend.app.services.extraction`
- [ ] **Outcome 2**: `extract_prescription()` raises `NotMedicalDocumentError` when `doc_type == "other"`
- [ ] **Outcome 3**: `extract_prescription()` raises `ImageNotReadableError` when `overall_confidence < 0.3`
- [ ] **Outcome 4**: `_call_gpt4o_vision()` retries up to 3 times on `openai.RateLimitError` with exponential backoff
- [ ] **Outcome 5**: `_call_gpt4o_vision()` does NOT retry on `openai.AuthenticationError`
- [ ] **Outcome 6**: Image download failures (httpx errors) become `ImageNotReadableError`
- [ ] **Outcome 7**: All error logs include `request_id` when provided
- [ ] **Outcome 8**: Retry attempts are logged with attempt number before each sleep

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

**Exception classes (pure, no mocking):**
1. **test_extraction_error_is_exception**: `ExtractionError` inherits from `Exception`
2. **test_not_medical_document_error_inherits_extraction_error**: `NotMedicalDocumentError` is subclass of `ExtractionError`
3. **test_image_not_readable_error_inherits_extraction_error**: `ImageNotReadableError` is subclass of `ExtractionError`
4. **test_exception_classes_importable**: All three are importable from `backend.app.services.extraction`
5. **test_exception_message_preserved**: Instantiated with a message string, `str(exc)` returns it

**Semantic error detection:**
6. **test_raises_not_medical_document_for_doc_type_other**: Mock GPT-4O to return `doc_type="other"` -> raises `NotMedicalDocumentError`
7. **test_raises_image_not_readable_for_low_confidence**: Mock GPT-4O to return `overall_confidence=0.2` -> raises `ImageNotReadableError`
8. **test_no_error_for_prescription_doc_type**: Mock GPT-4O to return `doc_type="prescription"`, confidence=0.8 -> returns normally
9. **test_no_error_for_lab_report_doc_type**: Mock GPT-4O to return `doc_type="lab_report"`, confidence=0.7 -> returns normally
10. **test_confidence_threshold_boundary**: Mock with `overall_confidence=0.3` exactly -> does NOT raise (boundary is `< 0.3`)

**Tenacity retry:**
11. **test_retries_on_rate_limit_error**: Mock OpenAI to raise `RateLimitError` twice then succeed -> returns result
12. **test_retries_on_api_timeout_error**: Mock OpenAI to raise `APITimeoutError` once then succeed -> returns result
13. **test_retries_on_internal_server_error**: Mock OpenAI to raise `InternalServerError` once then succeed -> returns result
14. **test_retries_on_api_connection_error**: Mock OpenAI to raise `APIConnectionError` once then succeed -> returns result
15. **test_no_retry_on_authentication_error**: Mock OpenAI to raise `AuthenticationError` -> propagates immediately (1 call)
16. **test_no_retry_on_bad_request_error**: Mock OpenAI to raise `BadRequestError` -> propagates immediately (1 call)
17. **test_max_retries_exhausted**: Mock OpenAI to always raise `RateLimitError` -> raises after 3 attempts
18. **test_retry_logs_before_sleep**: Mock OpenAI to fail once then succeed -> verify retry log message emitted

**Image download error wrapping:**
19. **test_download_http_error_becomes_image_not_readable**: Mock httpx to raise `HTTPStatusError` -> raises `ImageNotReadableError`
20. **test_download_timeout_becomes_image_not_readable**: Mock httpx to raise `TimeoutException` -> raises `ImageNotReadableError`

### Mocking Strategy
- OpenAI `client.chat.completions.create()`: `AsyncMock` raising specific `openai.*Error` types
- `_download_image()`: mock for httpx error tests
- `_call_gpt4o_vision()`: mock for semantic error tests (return JSON strings)
- Tenacity `wait` and `stop` may need patching to speed up tests (avoid real delays)
- Use `tenacity.wait_none()` in tests to eliminate sleep

### Coverage Expectation
- All 3 exception classes tested
- All retry-eligible exception types tested (4 transient, 2 non-transient)
- Boundary condition on confidence threshold tested
- All public functions have at least one test; edge cases covered

---

## References
- roadmap.md (S5.5 row)
- specs/spec-S5.4-extract-prescription/ (predecessor spec)
- OpenAI Python SDK error hierarchy: `openai.APIError` subtypes
- Tenacity documentation: `@retry`, `stop_after_attempt`, `wait_exponential`, `retry_if_exception_type`
