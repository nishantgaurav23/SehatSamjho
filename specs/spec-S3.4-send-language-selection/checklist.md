# Checklist — Spec S3.4: Send Language Selection

## Phase 1: Setup & Dependencies
- [x] Verify S3.1 (SUPPORTED_LANGUAGES) is implemented and tests pass
- [x] Verify S3.3 (send_text_message) is implemented and tests pass
- [x] Locate target file: `backend/app/services/whatsapp.py`
- [x] No new pyproject.toml dependencies needed (uses existing Twilio + tenacity)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_send_language_selection.py`
- [x] Write tests for `build_language_menu_text()` (5 tests)
- [x] Write tests for `send_language_selection()` (6 tests)
- [x] Write tests for `send_more_languages()` (6 tests)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `build_language_menu_text()` — pure function, no deps
- [x] Implement `send_language_selection(to)` — text fallback + optional ContentSid
- [x] Implement `send_more_languages(to)` — remaining 14 languages sorted
- [x] Add PHI-safe logging (SHA-256 hash of phone numbers)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify function is importable: `from backend.app.services.whatsapp import send_language_selection`
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 6 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Phone numbers never logged in plaintext
- [x] Logging includes relevant context (to_hash, body_length)
- [x] Update roadmap.md status: pending -> done (when ready)
