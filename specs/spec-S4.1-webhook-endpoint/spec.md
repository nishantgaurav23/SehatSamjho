# Spec S4.1 — Webhook Endpoint

## Overview
Create the core `POST /webhook/whatsapp` endpoint in `webhooks.py`. This is the entry point for all incoming WhatsApp messages from Twilio. The endpoint parses the Twilio form body into a `WebhookPayload`, validates the request via HMAC signature (S1.5), and returns a minimal TwiML response. This spec does NOT implement session dispatch or state handlers — only the endpoint skeleton that accepts, validates, and parses incoming webhooks.

## Dependencies
- **S1.5** — Twilio HMAC verification (`validate_twilio_signature` dependency)
- **S2.2** — Async Redis client (Redis dependency injection via `get_redis()`)
- **S3.3** — `send_text_message()` (for error replies)

## Target Location
- `backend/app/api/webhooks.py`

---

## Functional Requirements

### FR-1: POST /webhook/whatsapp endpoint
- **What**: Add a `POST /webhook/whatsapp` route to the existing webhook router. The route must use `validate_twilio_signature` as a FastAPI dependency (via `Depends`).
- **Inputs**: Twilio form-encoded POST body with fields: `From`, `Body`, `NumMedia`, `MediaUrl0`, `MediaContentType0`
- **Outputs**: TwiML XML response (`<Response/>`) with `content-type: text/xml`
- **Edge cases**: Missing `From` field should return 400. Missing optional fields (`Body`, `NumMedia`, `MediaUrl0`, `MediaContentType0`) should use safe defaults (empty string, 0, None, None).

### FR-2: Parse Twilio form body into WebhookPayload
- **What**: Extract Twilio form fields from `request.form()` and construct a `WebhookPayload` Pydantic model. Field mapping: `From` → `from_number`, `Body` → `body`, `NumMedia` → `num_media` (int), `MediaUrl0` → `media_url`, `MediaContentType0` → `media_content_type`.
- **Inputs**: `request: Request` (FastAPI)
- **Outputs**: `WebhookPayload` instance
- **Edge cases**: `NumMedia` may be a string ("0", "1") — cast to int. Non-integer `NumMedia` → default to 0. Empty `From` → raise 400.

### FR-3: Return TwiML empty response
- **What**: Return a minimal TwiML `<Response/>` XML string as the HTTP response. Twilio requires this to acknowledge receipt. Status code 200, content-type `text/xml`.
- **Inputs**: None (static response)
- **Outputs**: `Response(content="<Response/>", media_type="text/xml")`
- **Edge cases**: None

### FR-4: Error handling with user-friendly reply
- **What**: If any unhandled exception occurs during webhook processing, catch it, log the error with `request_id`, send a generic error message to the user via `send_text_message()`, and still return TwiML `<Response/>` (Twilio must always get a 200 to avoid retries).
- **Inputs**: Exception, `from_number` (if available)
- **Outputs**: Error logged, text message sent to user, TwiML 200 returned
- **Edge cases**: If `from_number` is not yet parsed when the error occurs, skip the error message send. Never expose internal error details to the patient.

### FR-5: Request ID generation
- **What**: Generate a unique `request_id` (UUID4) at the start of each webhook invocation. Bind it to Loguru context for all downstream log statements. Pass it forward for use by dispatch/handlers (S4.2+).
- **Inputs**: None
- **Outputs**: `request_id: str` (UUID4 string)
- **Edge cases**: None

---

## Tangible Outcomes

- [ ] **Outcome 1**: `POST /webhook/whatsapp` returns 200 with `<Response/>` XML body when called with valid Twilio form data and valid HMAC signature
- [ ] **Outcome 2**: `POST /webhook/whatsapp` returns 403 when HMAC signature is invalid or missing (via S1.5 dependency)
- [ ] **Outcome 3**: `POST /webhook/whatsapp` returns 400 when `From` field is missing or empty
- [ ] **Outcome 4**: Twilio form fields are correctly parsed into a `WebhookPayload` model (including NumMedia string→int cast)
- [ ] **Outcome 5**: A unique `request_id` (UUID4) is generated per request and included in log output
- [ ] **Outcome 6**: Unhandled exceptions return TwiML 200 (not 500) and send an error message to the user
- [ ] **Outcome 7**: Response content-type is `text/xml`

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

1. **test_webhook_endpoint_exists**: Verify `POST /webhook/whatsapp` route exists on the router
2. **test_webhook_returns_twiml_response**: Valid request returns 200 with `<Response/>` body and `text/xml` content-type
3. **test_webhook_requires_hmac_dependency**: The endpoint has `validate_twilio_signature` as a dependency
4. **test_webhook_parses_from_field**: `From` field is extracted into `WebhookPayload.from_number`
5. **test_webhook_parses_body_field**: `Body` field is extracted into `WebhookPayload.body`
6. **test_webhook_parses_num_media**: `NumMedia` string is cast to int in `WebhookPayload.num_media`
7. **test_webhook_parses_media_url**: `MediaUrl0` field is extracted into `WebhookPayload.media_url`
8. **test_webhook_parses_media_content_type**: `MediaContentType0` field is extracted into `WebhookPayload.media_content_type`
9. **test_webhook_missing_from_returns_400**: Missing `From` field returns 400
10. **test_webhook_empty_from_returns_400**: Empty `From` field returns 400
11. **test_webhook_default_body_empty_string**: Missing `Body` defaults to empty string
12. **test_webhook_default_num_media_zero**: Missing `NumMedia` defaults to 0
13. **test_webhook_num_media_non_integer_defaults_zero**: Non-integer `NumMedia` (e.g., "abc") defaults to 0
14. **test_webhook_default_media_url_none**: Missing `MediaUrl0` defaults to None
15. **test_webhook_default_media_content_type_none**: Missing `MediaContentType0` defaults to None
16. **test_webhook_generates_request_id**: Each request produces a UUID4 request_id in logs
17. **test_webhook_error_returns_twiml_not_500**: Unhandled exception still returns 200 with TwiML (not 500)
18. **test_webhook_error_sends_message_to_user**: On error, `send_text_message()` is called with an apology message
19. **test_webhook_error_skips_send_if_no_from**: If error occurs before `From` is parsed, no send_text_message call
20. **test_webhook_logs_request_id**: Loguru log output includes the request_id

### Mocking Strategy
- **HMAC validation**: Override `validate_twilio_signature` dependency with a no-op in tests (already done for S1.4 tests, reuse pattern)
- **Redis**: Not directly used in S4.1 (dispatch is S4.2), but mock `get_redis` if imported
- **send_text_message**: Mock `backend.app.services.whatsapp.send_text_message` for error-reply tests
- **Loguru**: Use `loguru.logger.add(sink)` with a StringIO sink to capture log output for request_id assertions

### Coverage Expectation
- All public functions and edge cases covered
- 20 tests targeting endpoint behavior, parsing, defaults, error handling, and logging

---

## References
- roadmap.md (Phase 4 — Webhook State Machine)
- design.md, requirements.md
- S1.5 spec (Twilio HMAC verification)
- S2.4 spec (WebhookPayload model)
- S3.3 spec (send_text_message)
