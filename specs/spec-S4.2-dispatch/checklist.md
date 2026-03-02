# Checklist — Spec S4.2: Dispatch

## Phase 1: Setup & Dependencies
- [x] Verify S4.1 (webhook endpoint) is implemented and tests pass
- [x] Verify S2.2 (async Redis client) is implemented and tests pass
- [x] Verify S2.4 (Pydantic models) is implemented and tests pass
- [x] Locate target file: `backend/app/api/webhooks.py`

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/api/test_dispatch.py`
- [x] Write tests for session loading (tests 1–4)
- [x] Write tests for routing logic (tests 5–8)
- [x] Write tests for session persistence (tests 9–13)
- [x] Write tests for webhook integration (tests 14–15)
- [x] Write tests for handler stubs (tests 16–18)
- [x] Write tests for logging (tests 19–20)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Add constants: `SESSION_KEY_PREFIX`, `SESSION_TTL_SECONDS`, `PROCESSING_MESSAGE`
- [x] Implement `_session_key(from_number)` — returns Redis key string
- [x] Implement `_save_session(phone, session, redis)` — serialize + set with TTL
- [x] Implement `_delete_session(phone, redis)` — delete Redis key
- [x] Implement `_load_session(phone, redis)` — get + deserialize, handle corrupted JSON
- [x] Implement handler stubs: `_handle_welcome_state()`, `_handle_language_state()`, `_handle_image_state()`
- [x] Implement `_dispatch(payload, request_id, redis)` — load session, route to handler
- [x] Wire `_dispatch()` into `webhook_whatsapp()` endpoint
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `webhook_whatsapp()` obtains Redis client correctly
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test` — all tests pass (including S4.1 tests)

## Phase 5: Verification
- [x] All 20 tangible outcomes / tests checked
- [x] No hardcoded secrets
- [x] Logging includes request_id in all dispatch log lines
- [x] No PHI logged (phone numbers only used as Redis keys, never in logs)
- [x] Update roadmap.md status: pending -> done (when ready)
