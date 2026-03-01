# Checklist — Spec S3.5: Send Audio Message

## Phase 1: Setup & Dependencies
- [x] Verify S3.3 (send_text_message) is implemented and passing
- [x] Locate target file: `backend/app/services/whatsapp.py`
- [x] No new dependencies needed (Twilio, asyncio, tenacity, loguru already present)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_send_audio_message.py`
- [x] Write failing tests for FR-1 (send_audio_message: success, caption, default caption)
- [x] Write failing tests for FR-1 validation (empty to, empty media_url, whitespace variants)
- [x] Write failing tests for FR-2 (retry on TwilioRestException, exhausted retries)
- [x] Write failing tests for FR-3 (fallback: audio success, audio fail, both fail)
- [x] Write failing tests for FR-4 (PHI-safe logging: no raw phone, no full URL)
- [x] Write tests for singleton + asyncio.to_thread usage
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `send_audio_message()` with @retry decorator — pass validation + basic send tests
- [x] Add default caption logic — pass caption tests
- [x] Implement PHI-safe logging (hash phone, extract domain from URL) — pass logging tests
- [x] Implement `send_audio_message_with_fallback()` — pass fallback tests
- [x] Run tests — expect all pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] No router wiring needed (utility function, called by Phase 9/10)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 16 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes to_hash, media_url_domain (no PHI)
- [x] Update roadmap.md status: pending -> done (when ready)
