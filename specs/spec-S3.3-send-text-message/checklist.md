# Checklist — Spec S3.3: Send Text Message

## Phase 1: Setup & Dependencies
- [x] Verify S1.3 (pydantic-settings config) is implemented and passing
- [x] Locate target file: `backend/app/services/whatsapp.py`
- [x] Confirm `twilio` package is in `pyproject.toml` dependencies (from S1.1)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_send_text_message.py`
- [x] Write test: `test_get_twilio_client_returns_client`
- [x] Write test: `test_get_twilio_client_singleton`
- [x] Write test: `test_send_text_message_calls_twilio`
- [x] Write test: `test_send_text_message_uses_asyncio_to_thread`
- [x] Write test: `test_send_text_message_returns_sid`
- [x] Write test: `test_send_text_message_empty_body_raises`
- [x] Write test: `test_send_text_message_empty_to_raises`
- [x] Write test: `test_send_text_message_whitespace_body_raises`
- [x] Write test: `test_send_text_message_retries_on_twilio_error`
- [x] Write test: `test_send_text_message_exhausts_retries`
- [x] Write test: `test_send_text_message_no_retry_on_value_error`
- [x] Write test: `test_send_text_message_logs_no_raw_phone`
- [x] Write test: `test_send_text_message_logs_no_full_body`
- [x] Write test: `test_send_text_message_from_uses_settings`
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement FR-1: `_get_twilio_client()` — lazy singleton Twilio Client
- [x] Implement FR-2: `send_text_message(to, body)` — async wrapper with `asyncio.to_thread`
- [x] Implement FR-3: Tenacity retry decorator (3 attempts, 2s exponential backoff)
- [x] Implement FR-4: Loguru logging (hashed phone, body length, no PHI)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify function is importable: `from backend.app.services.whatsapp import send_text_message`
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 7 tangible outcomes checked
- [x] No hardcoded secrets (uses settings.TWILIO_*)
- [x] Logging never includes raw phone or full body
- [x] Tenacity retry works correctly (retry on TwilioRestException only)
- [x] Update roadmap.md status: spec-written -> done (when ready)
