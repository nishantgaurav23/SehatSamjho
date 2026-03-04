# Checklist — Spec S9.1: Bhashini TTS API Client

## Phase 1: Setup & Dependencies
- [x] Verify dependency S1.3 (pydantic-settings) is implemented and passing
- [x] Create target file: `backend/app/services/tts.py`
- [x] Verify `httpx` is already in `pyproject.toml` (used by extraction.py)
- [x] Verify `BHASHINI_API_KEY` and `BHASHINI_USER_ID` fields exist in `config.py`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_bhashini_client.py`
- [x] Write module & import tests (4 tests)
- [x] Write constants tests (2 tests)
- [x] Write httpx client tests (3 tests)
- [x] Write payload builder tests (4 tests)
- [x] Write `_call_bhashini()` tests (11 tests)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `BhashiniTTSError` exception class
- [x] Implement `BHASHINI_INFERENCE_URL` and `BHASHINI_TTS_GENDER` constants
- [x] Implement `_get_httpx_client()` / `_reset_httpx_client()` lazy singleton
- [x] Implement `_build_bhashini_payload(text, language_code)`
- [x] Implement `_call_bhashini(text, language_code, request_id)`
- [x] Add Loguru logging with request_id (no PHI)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify tts.py is importable from the app package
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 24 tangible outcome tests pass
- [x] No hardcoded secrets (API key from settings only)
- [x] Logging includes request_id where applicable
- [x] No PHI in logs (no text content, no audio content)
- [x] Update roadmap.md status: pending -> done (when ready)
