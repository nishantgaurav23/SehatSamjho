# Checklist — Spec S4.1: Webhook Endpoint

## Phase 1: Setup & Dependencies
- [x] Verify S1.5 (Twilio HMAC) is implemented and tests pass
- [x] Verify S2.2 (Async Redis) is implemented and tests pass
- [x] Verify S3.3 (send_text_message) is implemented and tests pass
- [x] Locate target file: `backend/app/api/webhooks.py` (existing stub)
- [x] Confirm `WebhookPayload` model exists in `backend/app/models/schemas.py`

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/api/test_webhook_endpoint.py`
- [x] Write test_webhook_endpoint_exists
- [x] Write test_webhook_returns_twiml_response
- [x] Write test_webhook_requires_hmac_dependency
- [x] Write test_webhook_parses_from_field
- [x] Write test_webhook_parses_body_field
- [x] Write test_webhook_parses_num_media
- [x] Write test_webhook_parses_media_url
- [x] Write test_webhook_parses_media_content_type
- [x] Write test_webhook_missing_from_returns_400
- [x] Write test_webhook_empty_from_returns_400
- [x] Write test_webhook_default_body_empty_string
- [x] Write test_webhook_default_num_media_zero
- [x] Write test_webhook_num_media_non_integer_defaults_zero
- [x] Write test_webhook_default_media_url_none
- [x] Write test_webhook_default_media_content_type_none
- [x] Write test_webhook_generates_request_id
- [x] Write test_webhook_error_returns_twiml_not_500
- [x] Write test_webhook_error_sends_message_to_user
- [x] Write test_webhook_error_skips_send_if_no_from
- [x] Write test_webhook_logs_request_id
- [x] Run make local-test — expect failures (Red)

## Phase 3: Implementation
- [x] Implement FR-1 — POST /webhook/whatsapp route with HMAC dependency
- [x] Implement FR-2 — Parse Twilio form body into WebhookPayload
- [x] Implement FR-3 — Return TwiML `<Response/>` with text/xml content-type
- [x] Implement FR-4 — Error handling: catch exceptions, send error reply, return TwiML 200
- [x] Implement FR-5 — Generate request_id (UUID4), bind to Loguru context
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Confirm router is already wired into app via `main.py` (done in S1.4)
- [x] Verify endpoint is accessible at `/webhook/whatsapp` via app routes
- [x] Run make local-lint
- [x] Run full test suite: make local-test

## Phase 5: Verification
- [x] All 7 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id in all log statements
- [x] Error replies never expose internal details to patient
- [x] TwiML always returned (even on error) to prevent Twilio retries
- [x] Update roadmap.md status: pending -> done (when ready)
