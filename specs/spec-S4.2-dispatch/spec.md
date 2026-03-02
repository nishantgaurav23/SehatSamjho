# Spec S4.2 — Dispatch

## Overview
The `_dispatch()` function is the central routing engine of the webhook state machine. It loads the current conversation session from Redis (keyed by phone number), determines which handler to invoke based on `SessionStatus`, and routes new users to the welcome flow. Each session has a 30-minute TTL in Redis, after which the conversation resets.

## Dependencies
- **S4.1** — Webhook router + POST endpoint (provides `WebhookPayload`, `request_id`, webhook entry point)
- **S2.2** — Async Redis client (provides `get_redis()` for session storage)
- **S2.4** — Pydantic models (provides `SessionState`, `SessionStatus`, `WebhookPayload`)

## Target Location
`backend/app/api/webhooks.py`

---

## Functional Requirements

### FR-1: Load session from Redis
- **What**: Given a phone number, load the session JSON from Redis key `session:{phone_number}`. Deserialize into `SessionState` using Pydantic's `model_validate_json()`.
- **Inputs**: `phone_number: str` (from `WebhookPayload.from_number`), Redis client instance
- **Outputs**: `SessionState | None` — returns `None` if key does not exist
- **Edge cases**:
  - Key does not exist → treat as new user (return `None`)
  - Corrupted/invalid JSON in Redis → log warning, delete the key, treat as new user
  - Redis connection error → let exception propagate (caught by webhook error handler)

### FR-2: Route to handler based on SessionStatus
- **What**: `_dispatch()` inspects `SessionState.status` and calls the appropriate handler. For S4.2, the handlers are stubs (placeholder `async def` functions that will be implemented in S4.3–S4.5). The routing logic itself is the deliverable.
- **Routing table**:
  | `SessionState.status` | Handler |
  |---|---|
  | `None` (no session) | `_handle_welcome_state()` |
  | `WAITING_FOR_LANGUAGE` | `_handle_language_state()` |
  | `WAITING_FOR_IMAGE` | `_handle_image_state()` |
  | `PROCESSING` | Send "still processing" text, return |
- **Inputs**: `payload: WebhookPayload`, `request_id: str`, Redis client
- **Outputs**: None (handlers send WhatsApp messages as side effects)
- **Edge cases**:
  - Unknown/unexpected status value → log error, delete session, route to welcome

### FR-3: Session TTL
- **What**: Every time a session is written or updated in Redis, set TTL to 1800 seconds (30 minutes). Use Redis `SET` with `EX` parameter or `SETEX`.
- **Inputs**: Redis client, session key, serialized `SessionState`
- **Outputs**: Session stored in Redis with TTL
- **Edge cases**: TTL renewal on every interaction (not just creation)

### FR-4: Save session helper
- **What**: `_save_session()` serializes a `SessionState` to JSON and stores in Redis with TTL. Used by dispatch and all handlers.
- **Inputs**: `phone_number: str`, `session: SessionState`, Redis client
- **Outputs**: None (side effect: Redis key set)
- **Edge cases**: Overwrites any existing session for that phone number

### FR-5: Delete session helper
- **What**: `_delete_session()` removes the session key from Redis. Used when conversation ends or session is corrupted.
- **Inputs**: `phone_number: str`, Redis client
- **Outputs**: None (side effect: Redis key deleted)

### FR-6: Wire _dispatch() into webhook endpoint
- **What**: Replace the `# S4.2+ will add dispatch logic here` comment in `webhook_whatsapp()` with a call to `_dispatch(payload, request_id, redis_client)`. The Redis client is obtained via `get_redis()` as a FastAPI dependency or direct import.
- **Inputs**: Existing `webhook_whatsapp()` function
- **Outputs**: Updated endpoint that calls `_dispatch()` before returning TwiML

### FR-7: Handler stubs
- **What**: Create stub functions for the three handlers that will be implemented in S4.3–S4.5. Each stub should be an `async def` that logs a "not implemented" warning and sends a generic "Coming soon" text message to the user.
- **Stubs**:
  - `_handle_welcome_state(payload, request_id, redis)` → S4.3
  - `_handle_language_state(payload, session, request_id, redis)` → S4.4
  - `_handle_image_state(payload, session, request_id, redis)` → S4.5

### FR-8: Session key format
- **What**: The Redis key for a session is `session:{from_number}` where `from_number` is the full Twilio phone string (e.g., `whatsapp:+919876543210`). This is a constant prefix.
- **Inputs**: `from_number: str`
- **Outputs**: `str` — the Redis key

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_dispatch()` loads session from Redis and routes to the correct handler based on `SessionStatus`
- [ ] **Outcome 2**: New users (no session in Redis) are routed to `_handle_welcome_state()`
- [ ] **Outcome 3**: Sessions are stored with 30-minute TTL in Redis
- [ ] **Outcome 4**: `_save_session()` serializes `SessionState` to JSON and stores with TTL
- [ ] **Outcome 5**: `_delete_session()` removes session key from Redis
- [ ] **Outcome 6**: Corrupted session JSON is handled gracefully (log + delete + welcome)
- [ ] **Outcome 7**: `PROCESSING` state sends "still processing" message without re-triggering pipeline
- [ ] **Outcome 8**: `webhook_whatsapp()` calls `_dispatch()` with Redis client
- [ ] **Outcome 9**: Handler stubs exist and log warnings when called
- [ ] **Outcome 10**: Loguru logging includes `request_id` in all dispatch log lines

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

#### Session loading
1. **test_dispatch_new_user_no_session**: No Redis key → `_dispatch()` routes to welcome handler
2. **test_dispatch_loads_existing_session**: Valid session JSON in Redis → correct handler called
3. **test_dispatch_corrupted_session_json**: Invalid JSON in Redis → deletes key, routes to welcome
4. **test_dispatch_redis_key_format**: Session key is `session:{from_number}`

#### Routing
5. **test_dispatch_routes_waiting_for_language**: Session with `WAITING_FOR_LANGUAGE` → `_handle_language_state()`
6. **test_dispatch_routes_waiting_for_image**: Session with `WAITING_FOR_IMAGE` → `_handle_image_state()`
7. **test_dispatch_routes_processing**: Session with `PROCESSING` → sends "still processing" message
8. **test_dispatch_routes_unknown_status**: Unknown status → deletes session, routes to welcome

#### Session persistence
9. **test_save_session_stores_json**: `_save_session()` writes valid JSON to Redis
10. **test_save_session_sets_ttl**: `_save_session()` sets 30-minute (1800s) TTL
11. **test_save_session_overwrites_existing**: `_save_session()` replaces prior session
12. **test_delete_session_removes_key**: `_delete_session()` calls Redis DEL on session key
13. **test_delete_session_nonexistent_key_no_error**: `_delete_session()` on missing key does not raise

#### Integration with webhook endpoint
14. **test_webhook_calls_dispatch**: POST to `/webhook/whatsapp` with valid payload triggers `_dispatch()`
15. **test_webhook_returns_twiml_after_dispatch**: Endpoint still returns `<Response/>` after dispatch

#### Handler stubs
16. **test_welcome_stub_is_callable**: `_handle_welcome_state()` is an async function
17. **test_language_stub_is_callable**: `_handle_language_state()` is an async function
18. **test_image_stub_is_callable**: `_handle_image_state()` is an async function

#### Logging
19. **test_dispatch_logs_session_status**: Dispatch logs the current session status with request_id
20. **test_dispatch_logs_new_user**: Dispatch logs "New user" for sessions that don't exist

### Mocking Strategy
- **Redis**: Mock the Redis client (`AsyncMock`). Mock `get()`, `set()`, `delete()` methods.
- **Handler stubs**: Use `unittest.mock.patch` to verify dispatch calls the correct handler.
- **send_text_message**: Mock to verify "still processing" message for PROCESSING state.
- **Twilio HMAC**: Mock `validate_twilio_signature` dependency for endpoint tests.

### Coverage Expectation
- All public and private functions have at least one test
- Edge cases (corrupted JSON, missing session, unknown status) covered
- All three routing paths verified with mock assertions

---

## Constants

```python
SESSION_KEY_PREFIX = "session:"
SESSION_TTL_SECONDS = 1800  # 30 minutes
PROCESSING_MESSAGE = "Your prescription is still being processed. Please wait a moment."
```

---

## References
- roadmap.md — Phase 4: Webhook State Machine
- design.md — Session state machine flow
- `backend/app/models/schemas.py` — `SessionState`, `SessionStatus`, `WebhookPayload`
- `backend/app/db/redis.py` — `get_redis()`, async Redis client
- `backend/app/api/webhooks.py` — existing POST endpoint from S4.1
