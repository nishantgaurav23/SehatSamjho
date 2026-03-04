# Checklist — Spec S7.4: simplify_and_translate()

## Phase 1: Setup & Dependencies
- [x] Verify S7.2 (_build_system_prompt) is implemented and tests pass
- [x] Verify S7.3 (_build_user_prompt) is implemented and tests pass
- [x] Verify S5.5 (error taxonomy) pattern is implemented
- [x] Confirm TranslationResult schema exists in schemas.py
- [x] Confirm translation.py has _get_client(), CLAUDE_MODEL, TRANSLATION_MAX_TOKENS, TRANSLATION_TEMPERATURE

## Phase 2: Tests First (TDD)
- [x] Write test file: backend/tests/services/test_translate.py
- [x] Write 3 import & signature tests (Red)
- [x] Write 5 happy path tests (Red)
- [x] Write 5 response parsing tests (Red)
- [x] Write 4 edge case tests (Red)
- [x] Write 3 logging tests (Red)
- [x] Run make local-test — expect 20 failures (Red)

## Phase 3: Implementation
- [x] Implement simplify_and_translate() — prompt building
- [x] Implement Claude API call with correct params
- [x] Implement response text extraction
- [x] Implement TranslationResult parsing (text, summaries, disclaimer)
- [x] Implement logging with request_id (PHI-safe)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify function is importable from translation module
- [x] Run make local-lint
- [x] Run full test suite: make local-test (808 passed)

## Phase 5: Verification
- [x] All 20 tests pass
- [x] All tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id
- [x] Never logs PHI (translated text, prescription content)
- [x] Update roadmap.md status: spec-written -> done
