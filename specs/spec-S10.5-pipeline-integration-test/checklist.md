# Checklist — Spec S10.5: Pipeline Integration Test

## Phase 1: Setup & Dependencies
- [x] Verify S10.1 (pipeline wiring) is implemented and tests pass
- [x] Verify S10.2 (format reply) is implemented and tests pass
- [x] Verify S10.3 (format audio text) is implemented and tests pass
- [x] Verify S10.4 (pipeline errors) is implemented and tests pass
- [x] Confirm `backend/tests/api/conftest.py` sets required env vars

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/api/test_pipeline.py`
- [x] Write T1: test_pipeline_test_file_exists
- [x] Write T2: test_happy_path_http_200
- [x] Write T3: test_happy_path_sends_text_reply
- [x] Write T4: test_happy_path_sends_audio
- [x] Write T5: test_happy_path_logs_interaction_success
- [x] Write T6: test_happy_path_session_deleted
- [x] Write T7: test_happy_path_ack_before_pipeline
- [x] Write T8: test_request_id_threaded_to_all_services
- [x] Write T9: test_extraction_receives_correct_args
- [x] Write T10: test_translation_receives_glossary_context
- [x] Write T11: test_audio_text_formatted_for_tts
- [x] Write T12: test_reply_within_whatsapp_limit
- [x] Write T13: test_audio_text_within_tts_limit
- [x] Write T14: test_not_medical_doc_error_sends_message
- [x] Write T15: test_image_not_readable_error_sends_message
- [x] Write T16: test_translation_error_sends_message
- [x] Write T17: test_generic_error_sends_message
- [x] Write T18: test_error_logs_interaction_with_error_status
- [x] Write T19: test_audio_none_skips_audio_send
- [x] Write T20: test_error_still_cleans_session
- [x] Run `python -m pytest tests/api/test_pipeline.py -v --tb=short` — expect failures (Red)

## Phase 3: Implementation
- [x] No new production code needed — this is a test-only spec
- [x] Fix any test failures due to mock setup or assertion issues
- [x] Run tests — expect all 20 pass (Green)

## Phase 4: Integration
- [x] Run `make local-lint` — no lint errors
- [x] Run full test suite: `make local-test` — all tests pass (including new 20)

## Phase 5: Verification
- [x] All 20 tests pass
- [x] All tangible outcomes checked
- [x] No hardcoded secrets in test file
- [x] Mocking strategy covers all external services
- [x] Both happy path and error paths verified
- [x] Update roadmap.md status: spec-written → done
