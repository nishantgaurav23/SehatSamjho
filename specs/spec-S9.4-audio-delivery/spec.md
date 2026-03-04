# Spec S9.4 — Audio Delivery Orchestrator

## Overview
Orchestrates the full audio delivery pipeline: calls `text_to_speech()` (S9.2) to convert translated text into audio bytes via Bhashini TTS, then calls `_upload_to_s3()` (S9.3) to upload the audio and obtain a presigned URL. Returns the presigned URL for downstream WhatsApp delivery. This is the public API consumed by Phase 10 pipeline wiring.

## Dependencies
- S9.2 (`text_to_speech()` — Bhashini TTS call + validation)
- S9.3 (`_upload_to_s3()` — S3 upload + presigned URL generation)

## Target Location
`backend/app/services/tts.py`

---

## Functional Requirements

### FR-1: `generate_and_deliver_audio()` function signature
- **What**: Async function that accepts translated text, language code, and optional request_id. Orchestrates TTS + S3 upload and returns a presigned URL string.
- **Inputs**: `text: str`, `language_code: str`, `request_id: str = ""`
- **Outputs**: `str` — S3 presigned URL pointing to the generated audio file
- **Edge cases**: Empty text, empty language_code should raise ValueError before calling any downstream service

### FR-2: Input validation
- **What**: Validate that `text` is non-empty (after stripping whitespace) and `language_code` is non-empty before invoking TTS or S3.
- **Inputs**: `text`, `language_code`
- **Outputs**: Raises `ValueError` with descriptive message on invalid input
- **Edge cases**: Whitespace-only text, None values

### FR-3: Orchestration — TTS then S3
- **What**: Call `text_to_speech(text, language_code, request_id)` to get audio bytes, then call `_upload_to_s3(audio_bytes, request_id)` to upload and get presigned URL. Steps must be sequential (S3 depends on TTS output).
- **Inputs**: Valid text + language_code + request_id
- **Outputs**: Presigned URL string from S3
- **Edge cases**: TTS failure propagated, S3 failure propagated

### FR-4: Error propagation
- **What**: If `text_to_speech()` raises `BhashiniTTSError` or `ValueError`, propagate as-is without catching. If `_upload_to_s3()` raises `S3UploadError` or `ValueError`, propagate as-is. Caller (Phase 10 / S9.5) handles error policy.
- **Inputs**: Any failing state from downstream
- **Outputs**: Exception re-raised to caller
- **Edge cases**: Ensure no swallowed exceptions; logging before propagation

### FR-5: Logging with request_id
- **What**: Log at start (text length, language, request_id), after TTS success (audio size), and after S3 success (URL length). Log elapsed time for full orchestration. All log lines include `request_id` for correlation.
- **Inputs**: request_id passed through all calls
- **Outputs**: Structured Loguru log lines
- **Edge cases**: Empty request_id should still work (logs with empty string)

### FR-6: Latency tracking
- **What**: Measure wall-clock time from function entry to presigned URL return. Log total latency in milliseconds.
- **Inputs**: `time.monotonic()` start/end
- **Outputs**: Log line with `latency_ms`
- **Edge cases**: If function fails mid-way, latency not logged (exception propagates first)

---

## Tangible Outcomes

- [ ] **Outcome 1**: `generate_and_deliver_audio` is importable from `backend.app.services.tts`
- [ ] **Outcome 2**: Calling with valid text + language returns a presigned URL string starting with `https://`
- [ ] **Outcome 3**: Empty/whitespace text raises `ValueError` without calling TTS or S3
- [ ] **Outcome 4**: Empty language_code raises `ValueError` without calling TTS or S3
- [ ] **Outcome 5**: `BhashiniTTSError` from `text_to_speech()` propagates to caller
- [ ] **Outcome 6**: `S3UploadError` from `_upload_to_s3()` propagates to caller
- [ ] **Outcome 7**: Loguru logs include request_id, text_length, audio_bytes, url_length, latency_ms
- [ ] **Outcome 8**: Function is async (returns a coroutine)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

1. **test_import**: `generate_and_deliver_audio` importable from `backend.app.services.tts`
2. **test_is_async**: Function is a coroutine function
3. **test_signature**: Accepts `text`, `language_code`, `request_id` params with correct defaults
4. **test_happy_path**: Mock `text_to_speech` + `_upload_to_s3` — returns presigned URL
5. **test_calls_tts_with_correct_args**: Verify `text_to_speech` called with text, language_code, request_id
6. **test_calls_s3_with_tts_output**: Verify `_upload_to_s3` called with audio bytes from TTS + request_id
7. **test_returns_presigned_url**: Return value is the string from `_upload_to_s3`
8. **test_empty_text_raises_valueerror**: Empty string raises ValueError
9. **test_whitespace_text_raises_valueerror**: Whitespace-only text raises ValueError
10. **test_empty_language_code_raises_valueerror**: Empty language_code raises ValueError
11. **test_valueerror_skips_tts**: On ValueError, `text_to_speech` is never called
12. **test_valueerror_skips_s3**: On ValueError, `_upload_to_s3` is never called
13. **test_tts_error_propagates**: `BhashiniTTSError` from TTS propagates to caller
14. **test_tts_error_skips_s3**: If TTS fails, `_upload_to_s3` is never called
15. **test_s3_error_propagates**: `S3UploadError` from S3 upload propagates to caller
16. **test_logs_start**: Log line at start includes request_id, language, text_length
17. **test_logs_tts_success**: Log line after TTS includes audio size
18. **test_logs_final_success**: Log line at end includes request_id, url_length, latency_ms
19. **test_request_id_passed_through**: request_id forwarded to both TTS and S3 calls
20. **test_empty_request_id_works**: Empty request_id does not raise — functions still called

### Mocking Strategy
- Mock `text_to_speech` (already tested in S9.2 — mock at module level)
- Mock `_upload_to_s3` (already tested in S9.3 — mock at module level)
- No real Bhashini/S3 calls in these tests

### Coverage Expectation
- All public function paths covered: happy path, input validation, TTS error, S3 error, logging
- 20 tests targeting `generate_and_deliver_audio()` exclusively

---

## References
- roadmap.md (S9.4 row)
- specs/spec-S9.2-text-to-speech/spec.md
- specs/spec-S9.3-s3-upload/spec.md
- backend/app/services/tts.py (existing implementation of S9.1–S9.3)
