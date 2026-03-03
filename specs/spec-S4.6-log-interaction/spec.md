# Spec S4.6 — Log Interaction

## Overview

Implements `_log_interaction()` in the webhook module. After every successful pipeline run, writes one metadata row to the `interaction_log` PostgreSQL table via the async SQLAlchemy session. The phone number is SHA-256 hashed before storage — raw phone numbers, image content, and extracted/translated text are **never** persisted (zero PHI).

## Dependencies

- **S4.1** — Webhook endpoint (provides `webhook_whatsapp`, `_parse_webhook_payload`)
- **S2.1** — Async SQLAlchemy engine (`get_db()`, `AsyncSessionLocal`)
- **S2.3** — `InteractionLog` ORM model + `InteractionStatus` enum

## Target Location

`backend/app/api/webhooks.py`

---

## Functional Requirements

### FR-1: `_hash_phone()` helper
- **What**: Pure function that returns the SHA-256 hex digest of a phone number string.
- **Inputs**: `phone_number: str` (raw, e.g. `"whatsapp:+919876543210"`)
- **Outputs**: `str` — 64-character lowercase hex digest
- **Edge cases**: Empty string still produces a valid hash (no crash). Deterministic — same input always produces same output.

### FR-2: `_log_interaction()` async function
- **What**: Creates an `InteractionLog` row and commits it via an async DB session.
- **Inputs**:
  - `phone_number: str` — raw phone (will be hashed, never stored raw)
  - `language_code: str` — e.g. `"hi"`, `"ta"`
  - `doc_type: str` — e.g. `"prescription"` (default)
  - `status: InteractionStatus` — `SUCCESS`, `ERROR`, or `FLAGGED`
  - `request_id: str` — for log correlation
  - `db: AsyncSession` — injected SQLAlchemy async session
  - `confidence_avg: float | None = None` — average extraction confidence
  - `latency_ms: int | None = None` — total pipeline latency in milliseconds
  - `error_code: str | None = None` — error identifier (only when status != SUCCESS)
- **Outputs**: None (side effect: row inserted into `interaction_log`)
- **Behaviour**:
  1. Hash the phone number via `_hash_phone()`
  2. Construct `InteractionLog` ORM instance with all fields
  3. `db.add(log_entry)` + `await db.flush()` (let `get_db()` handle commit)
  4. Log success at INFO level with `request_id`, `status`, `language_code` (no PHI)
- **Edge cases**:
  - DB error during flush: catch, log at ERROR level with `request_id`, re-raise (caller decides whether to suppress or propagate)
  - Never log raw phone number, only the hash

### FR-3: Zero PHI guarantee
- **What**: The function must never include raw phone numbers, image URLs, extracted text, or translated text in any log statement or database field.
- **Verification**: All Loguru calls use only `phone_hash`, `language_code`, `status`, `request_id`, `doc_type`.

### FR-4: Integration point
- **What**: `_log_interaction()` is designed to be called at the end of `_run_pipeline()` (Phase 10 wiring). For now, it is defined and tested as a standalone function. The actual call site will be added in S10.1.
- **Inputs/Outputs**: N/A — this FR describes the integration contract.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_hash_phone("whatsapp:+919876543210")` returns a 64-char hex string, deterministic
- [ ] **Outcome 2**: `_log_interaction()` inserts exactly one row into `interaction_log` via `db.add()` + `db.flush()`
- [ ] **Outcome 3**: The inserted row has `phone_hash` (64 chars), not raw phone number
- [ ] **Outcome 4**: `status` field accepts all three `InteractionStatus` values (SUCCESS, ERROR, FLAGGED)
- [ ] **Outcome 5**: Optional fields (`confidence_avg`, `latency_ms`, `error_code`) are stored when provided, `None` when omitted
- [ ] **Outcome 6**: DB errors during flush are caught, logged with `request_id`, and re-raised
- [ ] **Outcome 7**: No Loguru log line contains a raw phone number — only `phone_hash`
- [ ] **Outcome 8**: Function signature accepts `db: AsyncSession` parameter (FastAPI dependency injection ready)

---

## Test-Driven Requirements

### Tests to Write First (Red → Green)

1. **test_hash_phone_returns_64_char_hex**: `_hash_phone()` returns a 64-character lowercase hex string
2. **test_hash_phone_deterministic**: Same input always produces same output
3. **test_hash_phone_different_inputs**: Different phone numbers produce different hashes
4. **test_hash_phone_empty_string**: Empty string returns a valid 64-char hash (no crash)
5. **test_log_interaction_calls_db_add**: `db.add()` is called with an `InteractionLog` instance
6. **test_log_interaction_calls_db_flush**: `db.flush()` is awaited after `db.add()`
7. **test_log_interaction_hashes_phone**: The `phone_hash` field on the added row is `_hash_phone(phone_number)`, not the raw phone
8. **test_log_interaction_sets_language_code**: `language_code` field matches the input
9. **test_log_interaction_sets_doc_type_default**: `doc_type` defaults to `"prescription"`
10. **test_log_interaction_sets_status**: `status` field matches the input enum value
11. **test_log_interaction_sets_confidence_avg**: Optional `confidence_avg` is stored when provided
12. **test_log_interaction_sets_latency_ms**: Optional `latency_ms` is stored when provided
13. **test_log_interaction_sets_error_code**: Optional `error_code` is stored when provided
14. **test_log_interaction_optional_fields_none**: When optional fields omitted, they are `None` on the row
15. **test_log_interaction_status_success**: Works with `InteractionStatus.SUCCESS`
16. **test_log_interaction_status_error**: Works with `InteractionStatus.ERROR`
17. **test_log_interaction_status_flagged**: Works with `InteractionStatus.FLAGGED`
18. **test_log_interaction_db_error_logs_and_reraises**: DB flush error is logged at ERROR level and re-raised
19. **test_log_interaction_no_raw_phone_in_logs**: Captured Loguru output contains `phone_hash` but not the raw phone number
20. **test_log_interaction_logs_with_request_id**: Loguru output includes `request_id` in context

### Mocking Strategy

- `db` (AsyncSession): Use `AsyncMock` with `add` and `flush` methods
- Loguru: Use `loguru` sink capture (e.g. `io.StringIO` + `logger.add()`) to verify log content
- No external services needed — this is a pure DB write function

### Coverage Expectation

- All public functions (`_hash_phone`, `_log_interaction`) have full branch coverage
- Edge cases: empty phone, DB error, all three status values, optional fields present/absent
