# Checklist — Spec S5.5: Error Taxonomy + Retry

## Phase 1: Setup & Dependencies
- [x] Verify S5.4 (extract_prescription) is implemented and tests pass
- [x] Confirm `tenacity` is in pyproject.toml dependencies
- [x] Confirm `openai` is in pyproject.toml dependencies
- [x] Locate target file: `backend/app/services/extraction.py`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_extraction_errors.py`
- [x] Write 5 exception class tests (pure, no mocking)
- [x] Write 5 semantic error detection tests (mock GPT-4O response)
- [x] Write 8 tenacity retry tests (mock OpenAI errors)
- [x] Write 2 image download error wrapping tests (mock httpx)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Define `ExtractionError`, `NotMedicalDocumentError`, `ImageNotReadableError` classes
- [x] Add tenacity `@retry` decorator to `_call_gpt4o_vision()`
- [x] Add `before_sleep` logging callback for retry attempts
- [x] Add semantic checks in `extract_prescription()`: doc_type + confidence threshold
- [x] Wrap httpx download errors as `ImageNotReadableError` in `extract_prescription()`
- [x] Add `request_id` parameter to `extract_prescription()` and bind to log context
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify existing S5.1–S5.4 tests still pass (no regressions)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 20 tests passing
- [x] All tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id where applicable
- [x] Tenacity retries only on transient errors (4 types)
- [x] Non-transient errors propagate immediately (not retried)
- [x] Update roadmap.md status: spec-written -> done (when ready)
