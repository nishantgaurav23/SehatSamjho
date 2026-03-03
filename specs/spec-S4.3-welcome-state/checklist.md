# Checklist — Spec S4.3: Welcome State

## Phase 1: Setup & Dependencies
- [x] Verify S4.2 (dispatch) is implemented and tests pass
- [x] Verify S3.4 (send_language_selection) is implemented and tests pass
- [x] Locate target file: `backend/app/api/webhooks.py`
- [x] Confirm `send_language_selection` import is available from `backend.app.services.whatsapp`

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/api/test_welcome_state.py`
- [x] Write tests for WELCOME_MESSAGE constant (exists, non-empty, contains required content)
- [x] Write tests for welcome message sending (calls send_text_message with WELCOME_MESSAGE)
- [x] Write tests for language selection sending (calls send_language_selection with phone number)
- [x] Write tests for message ordering (welcome before language selection)
- [x] Write tests for session creation (WAITING_FOR_LANGUAGE, request_id, created_at, no language)
- [x] Write tests for dispatch integration (new user → welcome handler → session created)
- [x] Write tests for error propagation (send failures propagate)
- [x] Write tests for logging (request_id in context, no raw phone numbers)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Add `WELCOME_MESSAGE` constant to `webhooks.py`
- [x] Add `send_language_selection` import to `webhooks.py`
- [x] Replace `_handle_welcome_state()` stub with full implementation
  - [x] Send welcome/consent message via `send_text_message()`
  - [x] Send language selection via `send_language_selection()`
  - [x] Create `SessionState(status=WAITING_FOR_LANGUAGE, request_id=..., created_at=...)`
  - [x] Save session via `_save_session()`
  - [x] Add Loguru logging with request_id context
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify dispatch still routes new users to welcome handler correctly
- [x] Run S4.2 dispatch tests — confirm no regressions
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 18 tangible outcomes checked
- [x] No hardcoded secrets
- [x] No raw phone numbers in log output
- [x] Logging includes request_id where applicable
- [x] Function signature matches S4.2 stub
- [x] Update roadmap.md status: spec-written → done
