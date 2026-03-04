# Checklist — Spec S10.4: Pipeline Error Handler

## Phase 1: Setup & Dependencies
- [x] Verify S10.1 (pipeline wiring) is implemented and tests pass
- [x] Locate target file: `backend/app/api/webhooks.py`
- [x] Confirm error classes exist: `NotMedicalDocumentError`, `ImageNotReadableError`, `ExtractionError`, `TranslationError`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/api/test_pipeline_errors.py`
- [x] Write 5 constant tests (NOT_MEDICAL_DOC_MESSAGE, IMAGE_NOT_READABLE_MESSAGE, TRANSLATION_ERROR_MESSAGE, EXTRACTION_ERROR_MESSAGE, GENERIC_PIPELINE_ERROR_MESSAGE)
- [x] Write 3 function signature tests (importable, signature, sync)
- [x] Write 5 mapping tests (each exception type → correct message)
- [x] Write 1 subclass priority test
- [x] Write 4 pipeline integration tests (sends message, logs interaction, session cleanup, send failure)
- [x] Write 1 PHI-safety test (no PHI in constants)
- [x] Write 1 error_code test (classname extraction)
- [x] Run make local-test — expect failures (Red)

## Phase 3: Implementation
- [x] Add 5 error message constants to webhooks.py
- [x] Implement `_handle_pipeline_error(exc)` — isinstance chain returning correct message
- [x] Wire error handling into `_run_pipeline()` except block: catch exceptions, call `_handle_pipeline_error()`, send message, log interaction with error status
- [x] Handle send_text_message failure during error sending (try/except, log, don't re-raise)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `_run_pipeline()` error path works end-to-end with mocked services
- [x] Run make local-lint
- [x] Run full test suite: make local-test

## Phase 5: Verification
- [x] All 20 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id in error paths
- [x] No PHI in error messages or logs
- [x] Update roadmap.md status: pending → done (when ready)
