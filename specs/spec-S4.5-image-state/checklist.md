# Checklist — Spec S4.5: Image State

## Phase 1: Setup & Dependencies
- [x] Verify dependencies (S4.2, S3.3) are implemented and tests pass
- [x] Locate target file: `backend/app/api/webhooks.py`
- [x] Confirm existing stub `_handle_image_state()` is present

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/api/test_image_state.py`
- [x] Write tests for constants (PROCESSING_ACK_MESSAGE, NO_IMAGE_MESSAGE, UNSUPPORTED_MEDIA_MESSAGE)
- [x] Write tests for valid image path (ack, session update, field preservation, pipeline call, cleanup)
- [x] Write tests for no-media path (reminder sent, session unchanged)
- [x] Write tests for non-image media path (error sent, session unchanged)
- [x] Write tests for error propagation
- [x] Write tests for logging (request_id context, PHI-safe)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Define `PROCESSING_ACK_MESSAGE` constant (mentions wait time ~20–30 seconds)
- [x] Define `NO_IMAGE_MESSAGE` constant (asks for prescription photo)
- [x] Define `UNSUPPORTED_MEDIA_MESSAGE` constant (only images supported)
- [x] Implement `_run_pipeline()` placeholder (logs "not implemented", sends placeholder message, deletes session)
- [x] Implement `_handle_image_state()` — validate num_media and content type
- [x] Implement valid image path — send ack, update session to PROCESSING, call pipeline
- [x] Implement no-media path — send NO_IMAGE_MESSAGE, do not change session
- [x] Implement non-image media path — send UNSUPPORTED_MEDIA_MESSAGE, do not change session
- [x] Add Loguru logging with request_id context, no PHI
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify dispatch routes WAITING_FOR_IMAGE to the real handler (not stub)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 15 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id where applicable
- [x] No raw phone numbers or media URLs in logs
- [x] All 20 tests pass
- [x] Update roadmap.md status: pending → done (when ready)
