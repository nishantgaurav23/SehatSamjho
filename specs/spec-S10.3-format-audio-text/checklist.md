# Checklist — Spec S10.3: Format Audio Text

## Phase 1: Setup & Dependencies
- [x] Verify dependency S7.4 (simplify_and_translate) is implemented and tests pass
- [x] Locate target file: `backend/app/api/webhooks.py`
- [x] Review existing `_format_reply()` for patterns to follow
- [x] No new imports/dependencies needed in pyproject.toml

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/api/test_format_audio_text.py`
- [x] Write tests for FR-1 (signature, importable, sync)
- [x] Write tests for FR-2 (strip emoji, markdown, bullets, special chars)
- [x] Write tests for FR-3 (spoken sentence structure, medicine names, dosage)
- [x] Write tests for FR-4 (spoken disclaimer)
- [x] Write tests for FR-5 (length limit, truncation)
- [x] Write tests for FR-6 (pipeline wiring)
- [x] Write edge case tests (empty medicines, single medicine, no PHI)
- [x] Run make local-test — expect failures (Red)

## Phase 3: Implementation
- [x] Implement FR-2 — emoji/markdown/bullet stripping helper
- [x] Implement FR-3 — spoken sentence builder for medicines
- [x] Implement FR-4 — spoken disclaimer formatting
- [x] Implement FR-5 — length limit enforcement with sentence-boundary truncation
- [x] Implement FR-1 — `_format_audio_text()` orchestrating FR-2 through FR-5
- [x] Run tests — expect pass (Green) — 19/20 pass (T20 pipeline wiring is Phase 4)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Wire `_format_audio_text()` into `_run_pipeline()` step 5
- [x] Update `generate_and_deliver_audio()` call to use cleaned text
- [x] Update `send_audio_message_with_fallback()` fallback_text to use cleaned text
- [x] Run make local-lint
- [x] Run full test suite: make local-test — 1016/1016 passed

## Phase 5: Verification
- [x] All 20 tangible outcomes checked (20/20 tests passing)
- [x] No hardcoded secrets
- [x] Logging includes request_id where applicable (via logger.contextualize in pipeline)
- [x] No PHI in formatted audio text (T19 verifies)
- [x] Update roadmap.md status: spec-written -> done
