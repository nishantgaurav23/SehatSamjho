# Spec S4.3 — Welcome State

## Overview
The `_handle_welcome_state()` handler is the first interaction point for new WhatsApp users. When a user messages the bot for the first time (or after session expiry), this handler sends a consent/welcome message followed by language selection buttons, creates a new session in Redis with `status=WAITING_FOR_LANGUAGE`, and returns an empty TwiML response. This replaces the S4.2 stub implementation.

## Dependencies
- **S4.2** — `_dispatch()`, `_save_session()`, session helpers, `TWIML_EMPTY`
- **S3.4** — `send_language_selection()` (sends language menu via Twilio)

## Target Location
`backend/app/api/webhooks.py`

---

## Functional Requirements

### FR-1: Welcome/consent message
- **What**: Send a welcome text message to the user introducing SehatSamjho and providing consent information. The message explains what the service does (translate prescriptions into plain language + audio) and that no personal health data is stored.
- **Inputs**: `payload.from_number` (WhatsApp phone string)
- **Outputs**: Twilio message sent via `send_text_message()`
- **Edge cases**: If `send_text_message()` raises, the exception propagates up to the webhook error handler (S4.1)

### FR-2: Send language selection
- **What**: After the welcome message, send the language selection menu using `send_language_selection()` from S3.4. This presents the user with the top 8 Indian languages + "More" option.
- **Inputs**: `payload.from_number`
- **Outputs**: Language menu sent via `send_language_selection()`
- **Edge cases**: If `send_language_selection()` fails, exception propagates to webhook error handler

### FR-3: Create session with WAITING_FOR_LANGUAGE status
- **What**: After sending both messages, store a new `SessionState` in Redis with `status=WAITING_FOR_LANGUAGE`, `request_id` set to the current request_id, and `created_at` set to the current UTC ISO timestamp. Uses `_save_session()` from S4.2.
- **Inputs**: `payload.from_number`, `request_id`, Redis client
- **Outputs**: Session stored in Redis with 30-minute TTL (via `_save_session()`)
- **Edge cases**: Overwrites any stale session that may exist for this phone number

### FR-4: Logging with request_id
- **What**: Log the welcome handler invocation using Loguru with `request_id` in context. Log: handler entry, welcome message sent, language selection sent, session created.
- **Inputs**: `request_id`
- **Outputs**: Structured log lines with `request_id`
- **Edge cases**: Logging must never include raw phone numbers (PHI-safe) — use hashed phone if needed

### FR-5: Welcome message constant
- **What**: Define a module-level constant `WELCOME_MESSAGE` containing the welcome/consent text. This makes the message testable and easy to update.
- **Inputs**: None
- **Outputs**: `str` constant
- **Content**: Must include: (1) service name "SehatSamjho", (2) what it does (translates prescriptions), (3) privacy note (no personal data stored), (4) instruction to choose a language

### FR-6: Function signature compatibility
- **What**: The implemented `_handle_welcome_state()` must maintain the same signature as the S4.2 stub: `async def _handle_welcome_state(payload: WebhookPayload, request_id: str, redis) -> None`. No return value — all effects are side-effect based (send messages, save session).
- **Inputs**: `payload: WebhookPayload`, `request_id: str`, `redis` (async Redis client)
- **Outputs**: `None`

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_handle_welcome_state()` sends a welcome/consent text message to the user
- [ ] **Outcome 2**: `_handle_welcome_state()` sends language selection menu after the welcome message
- [ ] **Outcome 3**: A new `SessionState` with `status=WAITING_FOR_LANGUAGE` is saved in Redis
- [ ] **Outcome 4**: The session has `request_id` and `created_at` fields populated
- [ ] **Outcome 5**: `WELCOME_MESSAGE` constant exists and contains required content (service name, purpose, privacy note)
- [ ] **Outcome 6**: All log lines include `request_id` context
- [ ] **Outcome 7**: No raw phone numbers appear in log output (PHI-safe)
- [ ] **Outcome 8**: Function signature matches S4.2 stub (`payload, request_id, redis`)
- [ ] **Outcome 9**: Existing dispatch tests (S4.2) continue to pass after replacing the stub
- [ ] **Outcome 10**: The handler is called correctly for new users (no session) and unknown status reset flows

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

#### Welcome message
1. **test_welcome_sends_welcome_message**: `_handle_welcome_state()` calls `send_text_message()` with `WELCOME_MESSAGE`
2. **test_welcome_message_contains_service_name**: `WELCOME_MESSAGE` includes "SehatSamjho"
3. **test_welcome_message_contains_privacy_note**: `WELCOME_MESSAGE` includes privacy/no-data-stored note
4. **test_welcome_message_contains_purpose**: `WELCOME_MESSAGE` mentions prescription translation

#### Language selection
5. **test_welcome_sends_language_selection**: `_handle_welcome_state()` calls `send_language_selection()` with the user's phone number
6. **test_welcome_sends_messages_in_order**: Welcome text is sent before language selection (call order verified)

#### Session creation
7. **test_welcome_creates_session_waiting_for_language**: After sending messages, a `SessionState` with `status=WAITING_FOR_LANGUAGE` is saved in Redis
8. **test_welcome_session_has_request_id**: Saved session includes the `request_id` passed to the handler
9. **test_welcome_session_has_created_at**: Saved session includes a valid `created_at` ISO timestamp
10. **test_welcome_session_no_language_set**: Saved session has `language_code=None` and `language_name=None`

#### Integration with dispatch
11. **test_dispatch_calls_welcome_for_new_user**: `_dispatch()` with no existing session calls the real (non-stub) `_handle_welcome_state()`
12. **test_dispatch_welcome_creates_session**: Full flow: dispatch for new user → welcome handler → session exists in Redis after

#### Error propagation
13. **test_welcome_propagates_send_error**: If `send_text_message()` raises, exception is not caught by the handler
14. **test_welcome_propagates_language_selection_error**: If `send_language_selection()` raises, exception propagates

#### Logging
15. **test_welcome_logs_with_request_id**: Handler logs include `request_id` in context
16. **test_welcome_logs_no_raw_phone**: Log output does not contain raw phone numbers

#### Constant
17. **test_welcome_message_constant_exists**: `WELCOME_MESSAGE` is importable from `backend.app.api.webhooks`
18. **test_welcome_message_is_nonempty_string**: `WELCOME_MESSAGE` is a non-empty string

### Mocking Strategy
- **send_text_message**: `unittest.mock.patch("backend.app.api.webhooks.send_text_message")` — mock to verify call args and order
- **send_language_selection**: `unittest.mock.patch("backend.app.api.webhooks.send_language_selection")` — mock to verify it's called with correct phone number
- **Redis**: `AsyncMock` with `set()`, `get()`, `delete()` methods — verify session is saved with correct JSON and TTL
- **_save_session**: Can optionally mock or test via Redis mock depending on test scope
- **datetime**: Mock `datetime.utcnow()` or `datetime.now(UTC)` for deterministic `created_at` values

### Coverage Expectation
- All branches of `_handle_welcome_state()` covered
- Message ordering verified
- Session state serialization verified
- Error propagation paths verified
- PHI-safe logging confirmed

---

## References
- roadmap.md — Phase 4: Webhook State Machine, S4.3
- `backend/app/api/webhooks.py` — S4.2 stub to be replaced
- `backend/app/services/whatsapp.py` — `send_text_message()`, `send_language_selection()`
- `backend/app/models/schemas.py` — `SessionState`, `SessionStatus`, `WebhookPayload`
