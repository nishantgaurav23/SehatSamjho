# Checklist — Spec S9.5: Graceful Degradation

## Phase 1: Setup & Dependencies
- [x] Verify S9.4 (generate_and_deliver_audio) is implemented and tests pass
- [x] Locate target file: `backend/app/services/tts.py`
- [x] No new dependencies needed

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_graceful_degradation.py`
- [x] Write 20 failing tests covering all FRs
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Add `AUDIO_UNAVAILABLE_MESSAGE` constant to `tts.py`
- [x] Update `generate_and_deliver_audio()` return type to `str | None`
- [x] Wrap `text_to_speech()` call in try/except for `BhashiniTTSError`
- [x] Wrap `_upload_to_s3()` call in try/except for `S3UploadError`
- [x] Log `logger.warning()` on each degradation path with request_id
- [x] Return `None` on caught errors
- [x] Keep `ValueError` propagation unchanged
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify existing S9.1–S9.4 tests still pass (no regression)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 8 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id
- [x] Warning-level logs on degradation (not error)
- [x] Update roadmap.md status: pending -> done (when ready)
