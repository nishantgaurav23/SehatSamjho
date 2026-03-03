# Checklist — Spec S5.3: GPT-4O Vision Call

## Phase 1: Setup & Dependencies
- [x] Verify S5.1 (OpenAI client init) is implemented and tests pass
- [x] Verify S5.2 (extraction prompt) is implemented and tests pass
- [x] Locate target file: `backend/app/services/extraction.py`
- [x] Confirm `httpx` is already in `pyproject.toml` dependencies

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_gpt4o_vision_call.py`
- [x] Write 4 constant tests (GPT4O_MODEL, GPT4O_MAX_TOKENS, GPT4O_TEMPERATURE, GPT4O_IMAGE_DETAIL)
- [x] Write 5 `_encode_image_base64()` tests (pure function, no mocking)
- [x] Write 4 `_download_image()` tests (mock httpx)
- [x] Write 11 `_call_gpt4o_vision()` tests (mock _download_image + _get_client)
- [x] Run `make local-test` — expect 24 failures (Red)

## Phase 3: Implementation
- [x] Add `GPT4O_MODEL`, `GPT4O_MAX_TOKENS`, `GPT4O_TEMPERATURE`, `GPT4O_IMAGE_DETAIL` constants
- [x] Implement `_encode_image_base64()` — pure base64 encoding to data URI
- [x] Implement `_download_image()` — httpx async GET with 30s timeout
- [x] Implement `_call_gpt4o_vision()` — orchestrate download → encode → build messages → call OpenAI
- [x] Run tests — expect 24 pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify extraction.py exports are consistent (no public API changes needed — all functions are private)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 10 tangible outcomes checked
- [x] No hardcoded secrets (API key comes from `_get_client()` → settings)
- [x] No image bytes or base64 content logged (PHI safety)
- [x] Logging includes model name and token usage at debug level
- [x] Update roadmap.md status: spec-written → done
