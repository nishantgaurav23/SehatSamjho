# Checklist — Spec S2.2: Async Redis Client

## Phase 1: Setup & Dependencies
- [x] Verify dependencies S1.3 (config) and S1.4 (app factory) are implemented and passing
- [x] Confirm `redis>=4.5` is in pyproject.toml (from S1.1)
- [x] Create target file: `backend/app/db/redis.py`
- [x] Confirm `REDIS_URL` field exists in `backend/app/core/config.py` (from S1.3)

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/db/test_redis.py`
- [x] Write test_init_redis_creates_client
- [x] Write test_init_redis_calls_ping
- [x] Write test_init_redis_uses_redis_url
- [x] Write test_init_redis_decode_responses
- [x] Write test_init_redis_logs_success
- [x] Write test_get_redis_yields_client
- [x] Write test_get_redis_raises_before_init
- [x] Write test_close_redis_closes_client
- [x] Write test_close_redis_sets_none
- [x] Write test_close_redis_safe_without_init
- [x] Write test_close_redis_logs_message
- [x] Write test_lifespan_calls_init_redis
- [x] Write test_lifespan_calls_close_redis
- [x] Run `make local-test` — expect failures (Red) — 13/13 failing

## Phase 3: Implementation
- [x] Implement FR-1 (Redis client creation) — `_redis_client`, lazy via `init_redis()`
- [x] Implement FR-2 (`get_redis()`) — async generator yielding client
- [x] Implement FR-3 (`init_redis()`) — create client, ping, log success
- [x] Implement FR-4 (`close_redis()`) — close client, set None, log
- [x] Run `backend/tests/db/test_redis.py` — expect pass (Green) — 11/11 passing
- [x] Implement FR-5 (lifespan wiring) — update `main.py` lifespan
- [x] Run lifespan tests — expect pass (Green) — 13/13 passing
- [x] Refactor if needed — clean, no refactor needed

## Phase 4: Integration
- [x] Wire `init_redis()` / `close_redis()` into `main.py` lifespan
- [x] Update existing S1.4 lifespan tests to mock `init_redis`/`close_redis` (avoid breakage)
- [x] Run `make local-lint` — all checks passed
- [x] Run full test suite: `make local-test` — 95/95 passing

## Phase 5: Verification
- [x] All 13 tangible outcome tests pass — 95/95 full suite
- [x] No hardcoded secrets (REDIS_URL from settings only)
- [x] Logging includes appropriate messages via Loguru
- [x] `close_redis()` is safe to call unconditionally
- [x] No import-time side effects (client created lazily)
- [x] Update roadmap.md status: spec-written -> done
