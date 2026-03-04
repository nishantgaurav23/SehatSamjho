# Checklist — Spec S9.2: text_to_speech()

## Phase 1: Setup & Dependencies
- [x] Verify S9.1 (Bhashini TTS client) is implemented and tests passing
- [x] Locate target file: `backend/app/services/tts.py`
- [x] No new dependencies needed (tenacity already in pyproject.toml)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_text_to_speech.py`
- [x] Write import & signature tests (4 tests)
- [x] Write input validation tests (3 tests)
- [x] Write happy path tests (4 tests)
- [x] Write audio validation tests (3 tests)
- [x] Write retry tests (5 tests)
- [x] Write logging tests (3 tests)
- [x] Run `make local-test` — expect failures (Red) — 22/22 failing

## Phase 3: Implementation
- [x] Add `MAX_AUDIO_SIZE` constant to `tts.py`
- [x] Implement `text_to_speech()` with input validation (FR-1, FR-2)
- [x] Add audio size validation (FR-3)
- [x] Add tenacity `@retry` decorator (FR-4)
- [x] Add Loguru logging with request_id (FR-5)
- [x] Run tests — expect pass (Green) — 22/22 passing
- [x] Refactor if needed — clean, no changes needed

## Phase 4: Integration
- [x] Verify `text_to_speech()` is importable from `backend.app.services.tts`
- [x] Run `make local-lint` — ruff check + format pass
- [x] Run full test suite: `make local-test` — 894/894 passing

## Phase 5: Verification
- [x] All 22 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id
- [x] No PHI in logs (text content, audio bytes)
- [x] ValueError NOT retried, BhashiniTTSError IS retried
- [x] Update roadmap.md status: spec-written → done
