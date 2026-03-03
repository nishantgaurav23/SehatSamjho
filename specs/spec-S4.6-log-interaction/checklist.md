# Checklist — Spec S4.6: Log Interaction

## Phase 1: Setup & Dependencies
- [x] Verify S4.1 (webhook endpoint) is implemented and tests pass
- [x] Verify S2.1 (async SQLAlchemy engine) is implemented and tests pass
- [x] Verify S2.3 (interaction_log table) is implemented and tests pass
- [x] Locate target file: `backend/app/api/webhooks.py`
- [x] Confirm `InteractionLog` model and `InteractionStatus` enum importable from `backend.app.db.models`

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/api/test_log_interaction.py`
- [x] Write 4 tests for `_hash_phone()` (FR-1)
- [x] Write 16 tests for `_log_interaction()` (FR-2, FR-3)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Add `import hashlib` to `webhooks.py`
- [x] Add `from backend.app.db.models import InteractionLog, InteractionStatus` import
- [x] Implement `_hash_phone(phone_number: str) -> str` (FR-1)
- [x] Implement `_log_interaction()` async function (FR-2)
- [x] Ensure zero PHI in all log lines (FR-3)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] No router/dependency wiring needed (call site added in S10.1)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 20 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id in all log lines
- [x] No raw phone numbers in any log line or DB field
- [x] `_log_interaction()` accepts `db: AsyncSession` parameter
- [x] Update roadmap.md status: spec-written → done (when ready)
