# Spec S3.3 — Send Text Message

## Overview
Async wrapper around the Twilio WhatsApp API for sending text messages. Uses `asyncio.to_thread` to offload the synchronous Twilio SDK `messages.create()` call. Includes tenacity retry with exponential backoff on transient Twilio API errors. This is the foundational send primitive used by all higher-level messaging functions (S3.4 language selection, S3.5 audio messages, S4.x webhook handlers).

## Dependencies
- **S1.3** — pydantic-settings config (provides `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`)

## Target Location
- `backend/app/services/whatsapp.py` (append to existing file)

---

## Functional Requirements

### FR-1: Twilio Client Initialization
- **What**: Lazy-initialized module-level Twilio REST client singleton via `_get_twilio_client()`.
- **Inputs**: Uses `settings.TWILIO_ACCOUNT_SID` and `settings.TWILIO_AUTH_TOKEN` from config.
- **Outputs**: Returns a `twilio.rest.Client` instance. Reuses the same client across calls.
- **Edge cases**: Client is created on first call, not at import time (avoids import-time side effects; testable via mock).

### FR-2: `send_text_message(to, body)`
- **What**: Async function that sends a WhatsApp text message via Twilio.
- **Inputs**:
  - `to: str` — recipient phone number in WhatsApp format (e.g., `"whatsapp:+919876543210"`)
  - `body: str` — message text (max 1600 chars per WhatsApp limit)
- **Outputs**: Returns the Twilio message SID (`str`) on success.
- **Behaviour**:
  1. Gets Twilio client via `_get_twilio_client()`
  2. Calls `client.messages.create(from_=settings.TWILIO_WHATSAPP_FROM, to=to, body=body)` inside `asyncio.to_thread()` (Twilio SDK is synchronous)
  3. Logs the send attempt and result with `loguru` (include `to` phone hash, message SID — never log full body or raw phone)
  4. Returns the message SID string
- **Edge cases**:
  - Empty body: raise `ValueError("Message body cannot be empty")`
  - Empty `to`: raise `ValueError("Recipient cannot be empty")`
  - Twilio API errors (TwilioRestException): handled by retry logic (FR-3)

### FR-3: Retry via Tenacity
- **What**: `send_text_message` is decorated with tenacity retry for transient Twilio failures.
- **Configuration**:
  - `stop=stop_after_attempt(3)` — max 3 attempts
  - `wait=wait_exponential(multiplier=1, min=2, max=10)` — 2s, 4s backoff
  - `retry=retry_if_exception_type(TwilioRestException)` — only retry on Twilio SDK errors
  - `reraise=True` — re-raise the original exception after exhausting retries
- **Edge cases**: Non-Twilio exceptions (ValueError, etc.) are NOT retried — they propagate immediately.

### FR-4: Logging
- **What**: Log send attempts and outcomes using loguru.
- **Log on send**: `logger.info("Sending WhatsApp text", to_hash=sha256(to), body_length=len(body))`
- **Log on success**: `logger.info("WhatsApp text sent", message_sid=sid)`
- **Log on failure**: `logger.error("WhatsApp text send failed", error=str(e))`
- **Never log**: raw phone number, full message body (PHI compliance)

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_get_twilio_client()` returns a `twilio.rest.Client` instance using settings credentials
- [ ] **Outcome 2**: `send_text_message("whatsapp:+919876543210", "Hello")` calls `client.messages.create()` via `asyncio.to_thread` and returns a message SID
- [ ] **Outcome 3**: Empty body raises `ValueError`; empty `to` raises `ValueError`
- [ ] **Outcome 4**: `send_text_message` retries up to 3 times on `TwilioRestException` with exponential backoff
- [ ] **Outcome 5**: After 3 failed attempts, the original `TwilioRestException` is re-raised
- [ ] **Outcome 6**: Non-Twilio exceptions (e.g., `ValueError`) are NOT retried
- [ ] **Outcome 7**: Logs never contain raw phone numbers or full message bodies

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_get_twilio_client_returns_client**: Mock `twilio.rest.Client`, verify `_get_twilio_client()` returns a Client using settings credentials
2. **test_get_twilio_client_singleton**: Call `_get_twilio_client()` twice, verify same instance returned (lazy singleton)
3. **test_send_text_message_calls_twilio**: Mock client, call `send_text_message`, verify `messages.create()` called with correct `from_`, `to`, `body`
4. **test_send_text_message_uses_asyncio_to_thread**: Verify the synchronous Twilio call is wrapped in `asyncio.to_thread`
5. **test_send_text_message_returns_sid**: Mock client returning a message with `.sid`, verify return value
6. **test_send_text_message_empty_body_raises**: Call with `body=""`, expect `ValueError`
7. **test_send_text_message_empty_to_raises**: Call with `to=""`, expect `ValueError`
8. **test_send_text_message_whitespace_body_raises**: Call with `body="   "`, expect `ValueError`
9. **test_send_text_message_retries_on_twilio_error**: Mock client to raise `TwilioRestException` twice then succeed, verify 3 total calls
10. **test_send_text_message_exhausts_retries**: Mock client to always raise `TwilioRestException`, verify it re-raises after 3 attempts
11. **test_send_text_message_no_retry_on_value_error**: Mock client to raise `ValueError`, verify no retry (immediate propagation)
12. **test_send_text_message_logs_no_raw_phone**: Capture log output, verify raw phone number is not logged
13. **test_send_text_message_logs_no_full_body**: Capture log output, verify full message body is not logged
14. **test_send_text_message_from_uses_settings**: Verify `from_` parameter matches `settings.TWILIO_WHATSAPP_FROM`

### Mocking Strategy
- **Twilio Client**: Mock `twilio.rest.Client` — never make real API calls
- **Settings**: Mock or set env vars for `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`
- **asyncio.to_thread**: May need to mock or use `pytest-asyncio` to test async behavior
- **loguru**: Use `loguru` sink capture or `caplog` equivalent to assert log content

### Coverage Expectation
- All public functions have at least one test; edge cases covered
- 100% branch coverage on `send_text_message` (happy path, validation errors, retry paths)

---

## References
- roadmap.md — S3.3 row (Phase 3, WhatsApp Channel)
- design.md — WhatsApp service layer
- requirements.md — Twilio integration requirements
- Twilio Python SDK: `twilio.rest.Client`, `client.messages.create()`
- Tenacity: `@retry` decorator with `stop_after_attempt`, `wait_exponential`, `retry_if_exception_type`
