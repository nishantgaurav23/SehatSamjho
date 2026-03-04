# Spec S9.5 — Graceful Degradation

## Overview
If Bhashini TTS fails after retries or S3 upload fails, the audio pipeline should degrade gracefully. `generate_and_deliver_audio()` catches all downstream errors (BhashiniTTSError, S3UploadError) after retries are exhausted, logs a warning, and returns `None`. The caller (Phase 10 pipeline) handles `None` by sending a text-only reply with a note: "Audio not available, please read the text below." The text response must never be blocked by audio failure.

## Dependencies
- S9.4 (`generate_and_deliver_audio()` orchestrator)

## Target Location
- `backend/app/services/tts.py` (modify `generate_and_deliver_audio()`)

---

## Functional Requirements

### FR-1: Catch BhashiniTTSError and return None
- **What**: If `text_to_speech()` raises `BhashiniTTSError` (after tenacity retries exhausted), `generate_and_deliver_audio()` catches it, logs a warning with request_id and error details, and returns `None`.
- **Inputs**: Valid text + language_code that triggers a Bhashini failure
- **Outputs**: `None` (not an exception)
- **Edge cases**: Error after 1st attempt vs after all 3 retries — both should result in `None`

### FR-2: Catch S3UploadError and return None
- **What**: If `_upload_to_s3()` raises `S3UploadError`, `generate_and_deliver_audio()` catches it, logs a warning with request_id and error details, and returns `None`.
- **Inputs**: Valid audio bytes from TTS but S3 fails
- **Outputs**: `None` (not an exception)
- **Edge cases**: ClientError, network timeout, presigned URL generation failure

### FR-3: Propagate ValueError (not caught)
- **What**: `ValueError` from input validation (empty text, empty language_code) is NOT caught — it propagates to the caller as before. Only downstream service errors are degraded.
- **Inputs**: Empty text or language_code
- **Outputs**: `ValueError` raised
- **Edge cases**: Whitespace-only text

### FR-4: Warning-level logging on degradation
- **What**: When degrading, log at `logger.warning()` level (not error) with request_id, error type, and error message. Include enough detail for debugging but no PHI.
- **Inputs**: Any caught exception
- **Outputs**: Loguru warning entry
- **Edge cases**: None

### FR-5: Return type is `str | None`
- **What**: The return type annotation of `generate_and_deliver_audio()` changes from `str` to `str | None` to reflect the graceful degradation path.
- **Inputs**: N/A
- **Outputs**: Updated type annotation
- **Edge cases**: N/A

### FR-6: AUDIO_UNAVAILABLE_MESSAGE constant
- **What**: Define a module-level constant `AUDIO_UNAVAILABLE_MESSAGE` with value: `"Audio is not available at the moment. Please read the text below."` — exported for use by Phase 10 callers.
- **Inputs**: N/A
- **Outputs**: String constant
- **Edge cases**: N/A

---

## Tangible Outcomes

- [ ] **Outcome 1**: `generate_and_deliver_audio()` returns `None` (no exception) when Bhashini TTS fails
- [ ] **Outcome 2**: `generate_and_deliver_audio()` returns `None` (no exception) when S3 upload fails
- [ ] **Outcome 3**: `ValueError` still propagates for invalid inputs (not caught)
- [ ] **Outcome 4**: Warning log emitted on degradation with request_id and error info
- [ ] **Outcome 5**: Return type annotation is `str | None`
- [ ] **Outcome 6**: `AUDIO_UNAVAILABLE_MESSAGE` constant is defined and importable
- [ ] **Outcome 7**: Happy path (no errors) still returns presigned URL string as before
- [ ] **Outcome 8**: All existing S9.4 tests still pass (no regression)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_import_audio_unavailable_message**: `AUDIO_UNAVAILABLE_MESSAGE` is importable from `tts` module
2. **test_audio_unavailable_message_value**: Constant contains expected text
3. **test_return_type_annotation**: `generate_and_deliver_audio` return annotation is `str | None`
4. **test_bhashini_failure_returns_none**: When `text_to_speech` raises `BhashiniTTSError`, returns `None`
5. **test_s3_failure_returns_none**: When `_upload_to_s3` raises `S3UploadError`, returns `None`
6. **test_bhashini_failure_logs_warning**: On Bhashini failure, `logger.warning` is called with request_id
7. **test_s3_failure_logs_warning**: On S3 failure, `logger.warning` is called with request_id
8. **test_valueerror_not_caught_empty_text**: Empty text still raises `ValueError`
9. **test_valueerror_not_caught_empty_language**: Empty language_code still raises `ValueError`
10. **test_happy_path_still_returns_url**: When both TTS and S3 succeed, returns presigned URL string
11. **test_bhashini_failure_no_s3_call**: When TTS fails, `_upload_to_s3` is never called
12. **test_bhashini_failure_with_request_id_in_log**: Warning log includes the request_id passed in
13. **test_s3_failure_with_request_id_in_log**: Warning log includes the request_id passed in
14. **test_generic_exception_from_tts_not_caught**: Unexpected exceptions (e.g., `RuntimeError`) still propagate
15. **test_generic_exception_from_s3_not_caught**: Unexpected exceptions (e.g., `RuntimeError`) still propagate
16. **test_bhashini_failure_log_contains_error_type**: Warning log includes the exception class name
17. **test_s3_failure_log_contains_error_type**: Warning log includes the exception class name
18. **test_happy_path_logs_info_not_warning**: On success, only info logs (no warning)
19. **test_none_return_is_falsy**: Returned `None` on failure is falsy (for Phase 10 `if` check)
20. **test_existing_s9_4_tests_pass**: All prior S9.4 tests still pass (regression guard)

### Mocking Strategy
- Mock `text_to_speech` to raise `BhashiniTTSError` or return bytes
- Mock `_upload_to_s3` to raise `S3UploadError` or return URL string
- Mock `logger` to verify warning/info calls
- No real Bhashini/S3 calls

### Coverage Expectation
- All public functions have at least one test; edge cases covered
- Both degradation paths (TTS fail, S3 fail) fully tested
- Regression: happy path unchanged

---

## References
- roadmap.md Phase 9 table (S9.5 row)
- S9.4 spec (generate_and_deliver_audio)
- S9.1 spec (BhashiniTTSError)
- S9.3 spec (S3UploadError)
