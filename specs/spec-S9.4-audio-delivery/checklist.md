# Checklist — Spec S9.4: Audio Delivery Orchestrator

## Phase 1: Setup & Dependencies
- [x] Verify S9.2 (text_to_speech) is implemented and tests pass
- [x] Verify S9.3 (_upload_to_s3) is implemented and tests pass
- [x] Confirm target file exists: `backend/app/services/tts.py`
- [x] No new imports/dependencies needed (all already in tts.py)

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/services/test_audio_delivery.py`
- [x] Write 20 failing tests covering all FRs (import, async, signature, happy path, validation, error propagation, logging, request_id)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `generate_and_deliver_audio()` in `backend/app/services/tts.py`
  - [x] Input validation (FR-2): empty text, whitespace text, empty language_code → ValueError
  - [x] Logging at start with request_id, language, text_length (FR-5)
  - [x] Call `text_to_speech(text, language_code, request_id)` (FR-3)
  - [x] Log TTS success with audio size (FR-5)
  - [x] Call `_upload_to_s3(audio_bytes, request_id)` (FR-3)
  - [x] Log final success with url_length + latency_ms (FR-5, FR-6)
  - [x] Return presigned URL string
  - [x] Error propagation — no try/except wrapping BhashiniTTSError or S3UploadError (FR-4)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `generate_and_deliver_audio` is importable from `backend.app.services.tts`
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 8 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id in all log lines
- [x] Update roadmap.md status: spec-written → done
