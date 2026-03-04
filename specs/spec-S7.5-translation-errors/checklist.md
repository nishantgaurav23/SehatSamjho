# Checklist — Spec S7.5: Retry + Error Handling (Translation)

## Phase 1: Setup & Dependencies
- [x] Verify S7.4 (simplify_and_translate) is implemented and tests pass
- [x] Confirm tenacity is in pyproject.toml dependencies
- [x] Confirm anthropic exception classes are available (APITimeoutError, etc.)
- [x] Review S5.5 extraction errors pattern for consistency

## Phase 2: Tests First (TDD)
- [x] Write test file: backend/tests/services/test_translation_errors.py
- [x] Write 3 exception class tests (Red)
- [x] Write 5 retry decorator tests (Red)
- [x] Write 2 non-retryable error tests (Red)
- [x] Write 3 TranslationError raising tests (Red)
- [x] Write 4 retry logging tests (Red)
- [x] Write 3 integration tests (Red)
- [x] Run make local-test — expect 20 failures (Red)

## Phase 3: Implementation
- [x] Add TranslationError exception class
- [x] Add _log_translation_retry callback
- [x] Add @retry decorator to simplify_and_translate
- [x] Replace ValueError with TranslationError on empty response
- [x] Add TranslationError on whitespace-only response
- [x] Add language_code to error logs
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify TranslationError and simplify_and_translate importable
- [x] Verify existing S7.4 tests still pass (20/20)
- [x] Run make local-lint — clean
- [x] Run full test suite: make local-test (838 passed, 10 pre-existing S8.5 failures)

## Phase 5: Verification
- [x] All 20 tests pass
- [x] All tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id and language_code
- [x] Never logs PHI (translated text, prescription content)
- [x] Update roadmap.md status: spec-written -> done
