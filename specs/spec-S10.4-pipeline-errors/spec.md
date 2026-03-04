# Spec S10.4 — Pipeline Error Handler

## Overview
Maps exception types raised during the prescription pipeline (extraction, drug lookup, translation, TTS) to patient-friendly WhatsApp messages. Specific errors like `NotMedicalDocumentError` and `ImageNotReadableError` receive tailored guidance; all other exceptions get a generic "something went wrong" message. Errors are logged with `request_id` and recorded in the interaction_log table with appropriate error codes and `status=error`.

## Dependencies
- S10.1 (Pipeline wiring — `_run_pipeline()` in webhooks.py)

## Target Location
- `backend/app/api/webhooks.py` — `_handle_pipeline_error()` function + integration into `_run_pipeline()`

---

## Functional Requirements

### FR-1: `_handle_pipeline_error()` function
- **What**: Synchronous helper that maps an exception to a patient-friendly error message string
- **Inputs**: `exc: Exception` — the caught exception
- **Outputs**: `str` — patient-facing WhatsApp message (never exposes internals)
- **Mappings**:
  - `NotMedicalDocumentError` → `"This doesn't appear to be a medical document. Please send a photo of a prescription, lab report, or discharge summary."`
  - `ImageNotReadableError` → `"We couldn't read your image clearly. Please try again with better lighting and make sure the text is in focus."`
  - `TranslationError` → `"We had trouble translating your prescription. Please try sending the image again."`
  - `ExtractionError` (base class, catch-all for extraction issues not covered above) → `"We had trouble reading your prescription. Please try sending a clearer photo."`
  - Any other `Exception` → `"We're sorry, something went wrong while processing your prescription. Please try again in a moment."`
- **Edge cases**: subclasses of `NotMedicalDocumentError` / `ImageNotReadableError` should match their specific messages (isinstance check order matters)

### FR-2: Error message constants
- **What**: All patient-facing error messages defined as module-level constants
- **Constants**:
  - `NOT_MEDICAL_DOC_MESSAGE`
  - `IMAGE_NOT_READABLE_MESSAGE`
  - `TRANSLATION_ERROR_MESSAGE`
  - `EXTRACTION_ERROR_MESSAGE`
  - `GENERIC_PIPELINE_ERROR_MESSAGE`
- **Constraints**: No technical jargon, no stack traces, no PHI. Actionable guidance where possible (retry, better lighting, etc.)

### FR-3: Wire into `_run_pipeline()` exception handler
- **What**: The `_run_pipeline()` try/except block catches pipeline exceptions, calls `_handle_pipeline_error()`, sends the error message to the user, and logs the interaction as `status=error`
- **Inputs**: Exception from any pipeline step (extraction, enrichment, glossary, translation, TTS, sending)
- **Outputs**: Error message sent to user via `send_text_message()`, interaction logged with `status=InteractionStatus.ERROR`, `error_code` set to exception class name
- **Edge cases**: If `send_text_message()` itself fails while sending the error message, log the failure but do not re-raise (prevent infinite error loops)

### FR-4: Error code logging
- **What**: The exception class name (e.g., `"NotMedicalDocumentError"`, `"TranslationError"`) is recorded as `error_code` in the `_log_interaction()` call
- **Inputs**: The caught exception
- **Outputs**: `error_code=type(exc).__name__` passed to `_log_interaction()`
- **Edge cases**: error_code truncated to 100 chars if class name is unreasonably long

### FR-5: Session cleanup on error
- **What**: Session is always deleted from Redis after a pipeline error (already handled by `_run_pipeline()`'s `finally` block, but verify it works for error paths too)
- **Inputs**: `payload.from_number`, `redis`
- **Outputs**: Redis session key deleted

### FR-6: PHI-safe error logging
- **What**: Error log messages include `request_id` and `error_code` but never include phone numbers, image URLs, extracted text, or any patient data
- **Inputs**: Exception, request_id
- **Outputs**: Loguru log lines with `request_id` context, exception type, but no PHI

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_handle_pipeline_error(NotMedicalDocumentError())` returns `NOT_MEDICAL_DOC_MESSAGE`
- [ ] **Outcome 2**: `_handle_pipeline_error(ImageNotReadableError())` returns `IMAGE_NOT_READABLE_MESSAGE`
- [ ] **Outcome 3**: `_handle_pipeline_error(TranslationError())` returns `TRANSLATION_ERROR_MESSAGE`
- [ ] **Outcome 4**: `_handle_pipeline_error(ExtractionError())` returns `EXTRACTION_ERROR_MESSAGE`
- [ ] **Outcome 5**: `_handle_pipeline_error(ValueError("unexpected"))` returns `GENERIC_PIPELINE_ERROR_MESSAGE`
- [ ] **Outcome 6**: When pipeline raises `NotMedicalDocumentError`, user receives the tailored message via WhatsApp
- [ ] **Outcome 7**: When pipeline raises any error, interaction is logged with `status=error` and `error_code=<ExceptionClassName>`
- [ ] **Outcome 8**: When pipeline raises any error, session is cleaned up from Redis
- [ ] **Outcome 9**: Error log lines contain `request_id` but no PHI (no phone, no image URL, no extracted text)
- [ ] **Outcome 10**: If sending the error message itself fails, the failure is logged but does not crash the webhook

---

## Test-Driven Requirements

### Tests to Write First (Red → Green)
1. **test_handle_pipeline_error_importable**: `_handle_pipeline_error` is importable from `backend.app.api.webhooks`
2. **test_handle_pipeline_error_signature**: Accepts a single `exc: Exception` parameter, returns `str`
3. **test_handle_pipeline_error_is_sync**: Function is not a coroutine (synchronous)
4. **test_not_medical_doc_message_constant**: `NOT_MEDICAL_DOC_MESSAGE` is a non-empty string constant
5. **test_image_not_readable_message_constant**: `IMAGE_NOT_READABLE_MESSAGE` is a non-empty string constant
6. **test_translation_error_message_constant**: `TRANSLATION_ERROR_MESSAGE` is a non-empty string constant
7. **test_extraction_error_message_constant**: `EXTRACTION_ERROR_MESSAGE` is a non-empty string constant
8. **test_generic_pipeline_error_message_constant**: `GENERIC_PIPELINE_ERROR_MESSAGE` is a non-empty string constant
9. **test_maps_not_medical_document_error**: Returns `NOT_MEDICAL_DOC_MESSAGE` for `NotMedicalDocumentError`
10. **test_maps_image_not_readable_error**: Returns `IMAGE_NOT_READABLE_MESSAGE` for `ImageNotReadableError`
11. **test_maps_translation_error**: Returns `TRANSLATION_ERROR_MESSAGE` for `TranslationError`
12. **test_maps_extraction_error_base**: Returns `EXTRACTION_ERROR_MESSAGE` for base `ExtractionError`
13. **test_maps_generic_exception**: Returns `GENERIC_PIPELINE_ERROR_MESSAGE` for `ValueError`, `RuntimeError`, etc.
14. **test_subclass_priority**: A subclass of `NotMedicalDocumentError` still matches `NOT_MEDICAL_DOC_MESSAGE` (isinstance order)
15. **test_pipeline_error_sends_message**: Mock pipeline step to raise `NotMedicalDocumentError`, verify `send_text_message` called with tailored message
16. **test_pipeline_error_logs_interaction**: Mock pipeline to raise error, verify `_log_interaction` called with `status=ERROR`, `error_code` set
17. **test_pipeline_error_session_cleanup**: Mock pipeline to raise error, verify `_delete_session` still called
18. **test_pipeline_error_send_failure_handled**: Mock pipeline error + mock `send_text_message` to also raise — verify no crash, failure logged
19. **test_error_messages_no_phi**: All error message constants contain no placeholder for phone/name/image data
20. **test_error_code_from_exception_classname**: `error_code` matches `type(exc).__name__` for various exception types

### Mocking Strategy
- Mock `extract_prescription` to raise specific exceptions for pipeline error tests
- Mock `send_text_message` to verify error messages sent to user
- Mock `_log_interaction` or `AsyncSessionLocal` for DB interaction verification
- Mock `_delete_session` or Redis to verify session cleanup
- All external services (OpenAI, Anthropic, Twilio, Redis, DB) fully mocked

### Coverage Expectation
- All 5 error message constants tested
- All 5 exception→message mappings tested
- Pipeline integration (error→send→log→cleanup) tested
- Edge cases: send failure during error handling, subclass priority

---

## References
- roadmap.md — S10.4 row
- `backend/app/api/webhooks.py` — `_run_pipeline()`, existing error handling
- `backend/app/services/extraction.py` — `ExtractionError`, `NotMedicalDocumentError`, `ImageNotReadableError`
- `backend/app/services/translation.py` — `TranslationError`
