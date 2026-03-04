# Spec S10.5 — Pipeline Integration Test

## Overview
Full end-to-end integration test for the pipeline: sends a fake WhatsApp image webhook through the entire system (webhook endpoint → dispatch → image state handler → pipeline) with all external services mocked. Asserts correct Twilio send calls (text + audio), correct interaction log entry (status, latency, confidence), and correct session state cleanup. This is the capstone test for Phase 10 that validates all pipeline components (S10.1–S10.4) work together correctly when invoked through the webhook HTTP endpoint.

## Dependencies
- S10.1 (Pipeline wiring) — `_run_pipeline()` in webhooks.py
- S10.2 (Format reply) — `_format_reply()` in webhooks.py
- S10.3 (Format audio text) — `_format_audio_text()` in webhooks.py
- S10.4 (Pipeline error handler) — `_handle_pipeline_error()` in webhooks.py

## Target Location
- `backend/tests/api/test_pipeline.py`

---

## Functional Requirements

### FR-1: HTTP-level integration test (happy path)
- **What**: POST to `/webhook/whatsapp` with a fake Twilio image payload (valid HMAC, existing WAITING_FOR_IMAGE session in Redis) triggers the full pipeline end-to-end.
- **Inputs**: Twilio form data (From, Body, NumMedia=1, MediaUrl0, MediaContentType0=image/jpeg), Redis session with status=WAITING_FOR_IMAGE and language_code/language_name set.
- **Outputs**: HTTP 200 with TwiML `<Response/>`, text reply sent to user, audio sent to user, interaction logged to DB, session deleted from Redis.
- **Edge cases**: Verify the pipeline runs through all steps (extract → enrich → glossary → translate → format → TTS → send).

### FR-2: Correct Twilio message calls
- **What**: After pipeline completes, `send_text_message()` is called with the formatted reply text (containing medicine names, dosage, disclaimer) and `send_audio_message_with_fallback()` is called with the audio URL and fallback text.
- **Inputs**: Pipeline output data (PrescriptionData, TranslationResult, audio URL).
- **Outputs**: Exactly one `send_text_message` call with user's phone number + formatted reply, exactly one `send_audio_message_with_fallback` call with audio URL + fallback text.
- **Edge cases**: Audio URL is None → no audio send call.

### FR-3: Correct interaction log entry
- **What**: After successful pipeline, `_log_interaction()` is called with correct fields: phone hashed, language_code from session, status=SUCCESS, request_id, confidence_avg computed from medicines, latency_ms > 0.
- **Inputs**: Pipeline execution results.
- **Outputs**: One `_log_interaction()` call with all expected kwargs.
- **Edge cases**: Empty medicines list → confidence_avg is None.

### FR-4: Session cleanup
- **What**: After pipeline (success or failure), session is always deleted from Redis.
- **Inputs**: Any pipeline execution (success or error).
- **Outputs**: `_delete_session()` called with user's phone number.
- **Edge cases**: Even when pipeline raises an error, session cleanup still happens.

### FR-5: Pipeline error integration through HTTP
- **What**: When extraction raises `NotMedicalDocumentError`, the error handler sends the appropriate patient-friendly message, logs with status=ERROR, and cleans up the session — all through the HTTP endpoint.
- **Inputs**: POST to `/webhook/whatsapp` where `extract_prescription` raises `NotMedicalDocumentError`.
- **Outputs**: HTTP 200 (always), error message sent to user, interaction logged with status=ERROR and error_code.
- **Edge cases**: `ImageNotReadableError`, `TranslationError`, generic `Exception`.

### FR-6: Request ID threading end-to-end
- **What**: The UUID request_id generated in `webhook_whatsapp()` is passed through dispatch → image handler → pipeline → all service calls → log interaction.
- **Inputs**: Webhook invocation.
- **Outputs**: All mocked service calls receive the same request_id.

### FR-7: Processing acknowledgement sent before pipeline
- **What**: When the image handler receives a valid image, it sends the PROCESSING_ACK_MESSAGE text to the user before starting the pipeline.
- **Inputs**: Valid image webhook payload + WAITING_FOR_IMAGE session.
- **Outputs**: `send_text_message` called with PROCESSING_ACK_MESSAGE before any extraction call.

### FR-8: Response format validation
- **What**: The formatted reply text sent to the user contains medicine names, dosage, disclaimer, and respects the 1600-char WhatsApp limit. The formatted audio text contains medicine info without emoji/markdown and respects the 2000-char TTS limit.
- **Inputs**: Pipeline output data with multiple medicines.
- **Outputs**: Reply text ≤ 1600 chars, audio text ≤ 2000 chars, no emoji in audio text.

### FR-9: Audio fallback when TTS fails
- **What**: When `generate_and_deliver_audio()` returns None (TTS/S3 failure), the pipeline still sends the text reply successfully without attempting audio delivery.
- **Inputs**: Pipeline where TTS returns None.
- **Outputs**: Text reply sent, `send_audio_message_with_fallback` NOT called, interaction logged with status=SUCCESS.

### FR-10: Multiple error types through HTTP
- **What**: Different extraction/translation errors produce correct patient-facing messages when flowing through the full HTTP endpoint.
- **Inputs**: Various exception types raised by pipeline services.
- **Outputs**: Correct error message per exception type, HTTP 200 always returned.

---

## Tangible Outcomes

- [ ] **Outcome 1**: POST to `/webhook/whatsapp` with valid image payload → HTTP 200, text reply sent, audio sent, interaction logged, session deleted
- [ ] **Outcome 2**: All mocked service calls receive correct arguments (image_url, language_code, request_id, etc.)
- [ ] **Outcome 3**: `NotMedicalDocumentError` → HTTP 200 + patient-friendly error message sent + interaction logged with status=ERROR
- [ ] **Outcome 4**: Audio URL = None → text reply sent, no audio send call, interaction still logged as SUCCESS
- [ ] **Outcome 5**: PROCESSING_ACK_MESSAGE sent before pipeline execution begins
- [ ] **Outcome 6**: Formatted reply ≤ 1600 chars, formatted audio text ≤ 2000 chars with no emoji
- [ ] **Outcome 7**: All 20 tests pass with `python -m pytest tests/api/test_pipeline.py -v --tb=short`

---

## Test-Driven Requirements

### Tests to Write First (Red → Green)
1. **test_pipeline_test_file_exists**: Test file `test_pipeline.py` exists in `backend/tests/api/`
2. **test_happy_path_http_200**: POST webhook with image → HTTP 200 TwiML response
3. **test_happy_path_sends_text_reply**: Text reply sent with medicine names and disclaimer
4. **test_happy_path_sends_audio**: Audio message sent with presigned URL and fallback text
5. **test_happy_path_logs_interaction_success**: Interaction logged with status=SUCCESS, latency_ms, confidence_avg
6. **test_happy_path_session_deleted**: Session deleted from Redis after success
7. **test_happy_path_ack_before_pipeline**: PROCESSING_ACK_MESSAGE sent before extraction call
8. **test_request_id_threaded_to_all_services**: All services receive the same request_id
9. **test_extraction_receives_correct_args**: extract_prescription called with media_url, content_type, request_id
10. **test_translation_receives_glossary_context**: simplify_and_translate receives glossary_context from format_glossary_context
11. **test_audio_text_formatted_for_tts**: generate_and_deliver_audio receives formatted audio text (no emoji)
12. **test_reply_within_whatsapp_limit**: Formatted reply text ≤ 1600 chars
13. **test_audio_text_within_tts_limit**: Formatted audio text ≤ 2000 chars
14. **test_not_medical_doc_error_sends_message**: NotMedicalDocumentError → correct error message sent
15. **test_image_not_readable_error_sends_message**: ImageNotReadableError → correct error message sent
16. **test_translation_error_sends_message**: TranslationError → correct error message sent
17. **test_generic_error_sends_message**: RuntimeError → generic error message sent
18. **test_error_logs_interaction_with_error_status**: Error → interaction logged with status=ERROR + error_code
19. **test_audio_none_skips_audio_send**: TTS returns None → no audio send, text still sent, status=SUCCESS
20. **test_error_still_cleans_session**: Pipeline error → session still deleted from Redis

### Mocking Strategy
- **Twilio HMAC**: Override `validate_twilio_signature` FastAPI dependency to no-op
- **Redis**: Override `get_redis` dependency with mock Redis (returns preset session JSON)
- **External services**: Patch `extract_prescription`, `enrich_prescription`, `lookup_terms`, `format_glossary_context`, `simplify_and_translate`, `generate_and_deliver_audio` at module level in `backend.app.api.webhooks`
- **WhatsApp sends**: Patch `send_text_message`, `send_audio_message_with_fallback`
- **DB**: Patch `AsyncSessionLocal` with async context manager yielding mock session, patch `_log_interaction`
- **HTTP client**: Use `httpx.AsyncClient` with `ASGITransport` on the FastAPI app for true HTTP-level tests

### Coverage Expectation
- All 20 tests cover the full HTTP request → pipeline → response flow
- Both happy path and error paths tested
- All external services mocked — no real API calls

---

## References
- roadmap.md (S10.5 row)
- specs/spec-S10.1-pipeline-wiring/ (pipeline sequence)
- specs/spec-S10.2-format-reply/ (reply formatting)
- specs/spec-S10.3-format-audio-text/ (audio text formatting)
- specs/spec-S10.4-pipeline-errors/ (error handling)
- backend/tests/api/test_pipeline_wiring.py (existing unit-level pipeline tests)
