# Spec S10.1 — Pipeline Wiring

## Overview
Replace the Phase 4 placeholder `_run_pipeline()` in `webhooks.py` with the full end-to-end pipeline: call GPT-4O Vision extraction, enrich with drug lookup, look up glossary terms, translate with Claude Sonnet 4.6, generate TTS audio, and send the results to the patient via WhatsApp. A UUID `request_id` is threaded through every service call for log correlation. After the pipeline completes (success or failure), session is cleaned up and an interaction is logged.

## Dependencies
- S4.5 (`_handle_image_state()` — image validation + PROCESSING transition)
- S5.4 (`extract_prescription()` — GPT-4O Vision extraction)
- S6.3 (`lookup_terms()` — glossary Redis lookup)
- S6.4 (`format_glossary_context()` — format glossary for prompt)
- S7.4 (`simplify_and_translate()` — Claude translation)
- S8.4 (`enrich_prescription()` — drug lookup enrichment)
- S9.4 (`generate_and_deliver_audio()` — TTS + S3 + presigned URL)

## Target Location
`backend/app/api/webhooks.py` — replace `_run_pipeline()` stub

---

## Functional Requirements

### FR-1: Pipeline orchestration sequence
- **What**: `_run_pipeline()` executes the full pipeline in sequence: extract → enrich → glossary → translate → TTS → send
- **Inputs**: `payload` (WebhookPayload with media_url), `session` (SessionState with language_code/language_name), `request_id` (str), `redis` client
- **Outputs**: Side effects — sends translated text + audio to patient via WhatsApp
- **Sequence**:
  1. `extract_prescription(image_url=payload.media_url, content_type=payload.media_content_type, request_id=request_id)` → `PrescriptionData`
  2. `enrich_prescription(redis_client=redis, prescription=prescription_data, request_id=request_id)` → `list[DrugInfo | None]`
  3. Collect medical terms from `PrescriptionData.medicines[*].name` → `lookup_terms(terms, session.language_code, redis)` → `list[GlossaryEntry]`
  4. `format_glossary_context(glossary_entries, session.language_name)` → `str`
  5. `simplify_and_translate(prescription=prescription_data, language_name=session.language_name, language_code=session.language_code, drug_info_list=drug_info_list, glossary_context=glossary_context, request_id=request_id)` → `TranslationResult`
  6. `generate_and_deliver_audio(text=translation_result.translated_text, language_code=session.language_code, request_id=request_id)` → `str | None` (presigned URL or None)
  7. Send text reply to patient: `send_text_message(payload.from_number, translation_result.translated_text)`
  8. If audio URL is not None: `send_audio_message_with_fallback(payload.from_number, audio_url, fallback_text=translation_result.translated_text)`
  9. Clean up session: `_delete_session(payload.from_number, redis)`

### FR-2: Request ID threading
- **What**: The `request_id` (UUID4 string) must be passed to every service call for log correlation
- **Inputs**: `request_id` from `_handle_image_state()`
- **Outputs**: All service calls receive `request_id` parameter
- **Edge cases**: If a service doesn't accept request_id (e.g., `lookup_terms`, `format_glossary_context`), skip it — only pass where the signature supports it

### FR-3: Loguru context binding
- **What**: All pipeline log messages must include `request_id` via `logger.contextualize(request_id=request_id)`
- **Outputs**: Structured log messages with `request_id` for each pipeline step (start, after extraction, after enrichment, after translation, after TTS, after send)

### FR-4: Latency tracking
- **What**: Measure total pipeline wall-clock time (start to finish) in milliseconds
- **Inputs**: `time.monotonic()` at start and end
- **Outputs**: `latency_ms` integer passed to `_log_interaction()`

### FR-5: Confidence average calculation
- **What**: Compute average confidence from `PrescriptionData.medicines[*].confidence` (if present)
- **Inputs**: `PrescriptionData` after extraction
- **Outputs**: `confidence_avg` float (0.0–1.0) or None if no confidence scores available
- **Edge cases**: Empty medicines list → None, missing confidence fields → skip

### FR-6: Interaction logging on success
- **What**: After successful pipeline completion, call `_log_interaction()` with success status
- **Inputs**: phone_number, language_code, status=SUCCESS, request_id, db session, confidence_avg, latency_ms
- **Outputs**: One row in `interaction_log` table
- **Note**: Requires a DB session — use `get_db()` dependency or create one inline via `AsyncSessionLocal`

### FR-7: DB session acquisition
- **What**: `_run_pipeline()` needs an `AsyncSession` for `_log_interaction()` but is not called from a FastAPI route directly (no DI). Acquire a session via `AsyncSessionLocal()` context manager.
- **Inputs**: Import `AsyncSessionLocal` from `backend.app.db.database`
- **Outputs**: Async context manager providing `AsyncSession`, committed on success
- **Edge cases**: DB error during logging should not crash the pipeline — log and continue

### FR-8: Session cleanup
- **What**: After pipeline completes (success or failure), always delete the Redis session so the user can start a new conversation
- **Outputs**: `_delete_session(payload.from_number, redis)` called in a finally block or after both success and error paths

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_run_pipeline()` is no longer a placeholder — it calls all 6 services in sequence
- [ ] **Outcome 2**: Translated text is sent to the patient via `send_text_message()`
- [ ] **Outcome 3**: If audio URL is available, audio is sent via `send_audio_message_with_fallback()`
- [ ] **Outcome 4**: If audio is None (TTS/S3 failure), only text is sent (graceful degradation)
- [ ] **Outcome 5**: `request_id` appears in all log messages and is passed to all services that accept it
- [ ] **Outcome 6**: `_log_interaction()` is called with correct status, latency_ms, and confidence_avg
- [ ] **Outcome 7**: Session is deleted after pipeline completes (success or failure)
- [ ] **Outcome 8**: All imports are added (extraction, drug_lookup, glossary, translation, tts services)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

File: `backend/tests/api/test_pipeline_wiring.py`

1. **test_run_pipeline_exists_and_is_async**: Import `_run_pipeline`, verify it's an async function
2. **test_run_pipeline_signature**: Verify it accepts (payload, session, request_id, redis) parameters
3. **test_pipeline_calls_extract_prescription**: Mock all services, verify `extract_prescription()` called with correct args (media_url, content_type, request_id)
4. **test_pipeline_calls_enrich_prescription**: Verify `enrich_prescription()` called with redis, prescription_data, request_id
5. **test_pipeline_calls_lookup_terms**: Verify `lookup_terms()` called with medicine names list, language_code, redis
6. **test_pipeline_calls_format_glossary_context**: Verify `format_glossary_context()` called with glossary entries, language_name
7. **test_pipeline_calls_simplify_and_translate**: Verify `simplify_and_translate()` called with all correct args
8. **test_pipeline_calls_generate_and_deliver_audio**: Verify `generate_and_deliver_audio()` called with translated_text, language_code, request_id
9. **test_pipeline_sends_text_reply**: Verify `send_text_message()` called with from_number and translated_text
10. **test_pipeline_sends_audio_when_url_available**: When audio URL returned, verify `send_audio_message_with_fallback()` called
11. **test_pipeline_skips_audio_when_none**: When audio URL is None, verify `send_audio_message_with_fallback()` NOT called
12. **test_pipeline_deletes_session_on_success**: Verify `_delete_session()` called after successful pipeline
13. **test_pipeline_logs_interaction_on_success**: Verify `_log_interaction()` called with status=SUCCESS
14. **test_pipeline_latency_tracking**: Verify `_log_interaction()` receives latency_ms > 0
15. **test_pipeline_confidence_avg_calculated**: Verify confidence_avg is computed from PrescriptionData medicines
16. **test_pipeline_confidence_avg_none_when_empty**: Empty medicines list → confidence_avg is None
17. **test_pipeline_request_id_threaded**: Verify request_id passed to extract, enrich, translate, TTS calls
18. **test_pipeline_loguru_context**: Verify logger.contextualize called with request_id
19. **test_pipeline_session_deleted_on_error**: If extraction raises, session is still deleted
20. **test_pipeline_db_session_used_for_logging**: Verify AsyncSessionLocal used to acquire DB session

### Mocking Strategy
- **extraction.py**: `@patch("backend.app.api.webhooks.extract_prescription")`
- **drug_lookup.py**: `@patch("backend.app.api.webhooks.enrich_prescription")`
- **glossary.py**: `@patch("backend.app.api.webhooks.lookup_terms")`, `@patch("backend.app.api.webhooks.format_glossary_context")`
- **translation.py**: `@patch("backend.app.api.webhooks.simplify_and_translate")`
- **tts.py**: `@patch("backend.app.api.webhooks.generate_and_deliver_audio")`
- **whatsapp.py**: `@patch("backend.app.api.webhooks.send_text_message")`, `@patch("backend.app.api.webhooks.send_audio_message_with_fallback")`
- **DB**: `@patch("backend.app.api.webhooks.AsyncSessionLocal")`
- **Redis**: `AsyncMock()` for redis client
- **_log_interaction**: `@patch("backend.app.api.webhooks._log_interaction")`
- **_delete_session**: `@patch("backend.app.api.webhooks._delete_session")`

### Coverage Expectation
- All public functions have at least one test; edge cases covered
- 20 tests total

---

## References
- roadmap.md Phase 10 table
- S4.5 spec (image state handler)
- S5.4, S6.3, S6.4, S7.4, S8.4, S9.4 specs (service public APIs)
- design.md, requirements.md
