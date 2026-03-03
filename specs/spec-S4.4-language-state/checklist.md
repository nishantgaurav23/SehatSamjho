# Checklist — Spec S4.4: Language State

## Phase 1: Setup & Dependencies
- [x] Verify S4.2 (dispatch) is implemented and tests pass
- [x] Verify S3.2 (parse_language_selection) is implemented and tests pass
- [x] Verify S3.3 (send_text_message) is implemented and tests pass
- [x] Verify S3.4 (send_language_selection, send_more_languages) is implemented and tests pass
- [x] Locate target file: `backend/app/api/webhooks.py`
- [x] Confirm `parse_language_selection` and `send_more_languages` imports available from `backend.app.services.whatsapp`

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/api/test_language_state.py`
- [x] Write tests for constants (IMAGE_PROMPT_MESSAGE, LANGUAGE_NOT_RECOGNISED_MESSAGE)
- [x] Write tests for valid language selection (session update, message sent, request_id/created_at preserved)
- [x] Write tests for "More languages" path (sends extended list, re-sends menu, no session change)
- [x] Write tests for invalid input path (sends error, re-sends menu, no session change)
- [x] Write tests for error propagation (send failures propagate)
- [x] Write tests for logging (request_id in context, no raw phone numbers)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Add `parse_language_selection`, `send_more_languages` imports to `webhooks.py`
- [x] Add `IMAGE_PROMPT_MESSAGE` constant to `webhooks.py`
- [x] Add `LANGUAGE_NOT_RECOGNISED_MESSAGE` constant to `webhooks.py`
- [x] Replace `_handle_language_state()` stub with full implementation
  - [x] Check for "9" (More languages) → send extended list + re-send menu
  - [x] Call `parse_language_selection(payload.body)`
  - [x] If valid: update session (language_code, language_name, status=WAITING_FOR_IMAGE), save, send IMAGE_PROMPT_MESSAGE
  - [x] If invalid: send LANGUAGE_NOT_RECOGNISED_MESSAGE + re-send language selection
  - [x] Add Loguru logging with request_id context
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify dispatch still routes WAITING_FOR_LANGUAGE to language handler correctly
- [x] Run S4.2 dispatch tests — confirm no regressions
- [x] Run S4.3 welcome state tests — confirm no regressions
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 14 tangible outcomes checked
- [x] No hardcoded secrets
- [x] No raw phone numbers in log output
- [x] Logging includes request_id where applicable
- [x] Function signature matches S4.2 stub
- [x] Update roadmap.md status: pending → done (when ready)
