# Spec S2.2 — Async Redis Client

## Overview
Sets up the async Redis client, connection pool, and a FastAPI dependency (`get_redis()`) for injecting a Redis connection into endpoints. Uses `redis.asyncio` (the `redis>=4.5` async API, NOT the deprecated `aioredis` package which is broken on Python 3.11+). Provides `init_redis()` and `close_redis()` hooks for the app lifespan — ping on startup to verify connectivity, close pool on shutdown. Redis is used for WhatsApp session state, drug cache, and glossary cache throughout the project.

## Dependencies
- **S1.3** (pydantic-settings config) — provides `settings.REDIS_URL`
- **S1.4** (FastAPI app factory) — lifespan hooks for startup/shutdown integration

## Target Location
`backend/app/db/redis.py`

---

## Functional Requirements

### FR-1: Redis Client Creation
- **What**: Create an async Redis client using `redis.asyncio.from_url()` with the `REDIS_URL` from settings.
- **Inputs**: `settings.REDIS_URL` (string, `redis://...` format)
- **Outputs**: A `redis.asyncio.Redis` instance
- **Config**: `decode_responses=True` (return strings, not bytes), connection pool managed internally by `from_url()`
- **Lifecycle**: Module-level `_redis_client: Redis | None = None` — lazily created by `init_redis()`, never at import time (unlike the SQLAlchemy engine which reads settings at import). This avoids import-time connection attempts.
- **Edge cases**: Invalid REDIS_URL should raise at `init_redis()` (on ping), not at import time

### FR-2: `get_redis()` FastAPI Dependency
- **What**: An async generator that yields the module-level Redis client for use in endpoints.
- **Inputs**: None (called by FastAPI dependency injection)
- **Outputs**: Yields the `redis.asyncio.Redis` client
- **Behavior**:
  1. Check that `_redis_client` is not `None` (raise `RuntimeError` if `init_redis()` was not called)
  2. `yield _redis_client`
  3. No commit/rollback semantics (Redis is not transactional in this usage)
- **Edge cases**: If called before `init_redis()`, must raise `RuntimeError("Redis client not initialized. Call init_redis() first.")`

### FR-3: `init_redis()` Startup Hook
- **What**: Create the Redis client from settings, store in module-level `_redis_client`, and ping to verify connectivity.
- **Behavior**:
  1. `_redis_client = redis.asyncio.from_url(settings.REDIS_URL, decode_responses=True)`
  2. `await _redis_client.ping()` — raises `redis.ConnectionError` if Redis is unreachable
  3. Log success via Loguru: `"Redis connection verified successfully"`
- **Outputs**: Returns `None`. Sets `_redis_client` as side effect.
- **Edge cases**: If Redis is down, `ping()` raises — let it propagate (app should not start without Redis)

### FR-4: `close_redis()` Shutdown Hook
- **What**: Close the Redis connection pool cleanly.
- **Behavior**:
  1. If `_redis_client` is not `None`: `await _redis_client.close()`
  2. Set `_redis_client = None`
  3. Log: `"Redis connection closed"`
- **Outputs**: Returns `None`
- **Edge cases**: Safe to call even if `init_redis()` was never called (no-op when `_redis_client is None`)

### FR-5: Lifespan Wiring
- **What**: Wire `init_redis()` and `close_redis()` into the FastAPI lifespan in `main.py`.
- **Where**: `backend/app/main.py` — update the existing `lifespan()` to call `init_redis()` at startup and `close_redis()` at shutdown, alongside the existing `init_db()` / `close_db()` calls.
- **Order**: `init_db()` then `init_redis()` on startup; `close_redis()` then `close_db()` on shutdown (reverse order)

---

## Tangible Outcomes

- [ ] **Outcome 1**: `from backend.app.db.redis import get_redis` is importable and is an async generator
- [ ] **Outcome 2**: `init_redis()` creates a client, pings Redis, and logs success
- [ ] **Outcome 3**: `get_redis()` yields a `redis.asyncio.Redis` instance after `init_redis()` has been called
- [ ] **Outcome 4**: `get_redis()` raises `RuntimeError` if called before `init_redis()`
- [ ] **Outcome 5**: `close_redis()` closes the client and is safe to call unconditionally (even if never initialized)
- [ ] **Outcome 6**: `main.py` lifespan calls `init_redis()` on startup and `close_redis()` on shutdown

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_init_redis_creates_client**: After calling `init_redis()`, the module-level client should not be `None`
2. **test_init_redis_calls_ping**: Verify that `ping()` is called on the client during `init_redis()`
3. **test_init_redis_uses_redis_url**: Verify `from_url()` is called with `settings.REDIS_URL`
4. **test_init_redis_decode_responses**: Verify `from_url()` is called with `decode_responses=True`
5. **test_init_redis_logs_success**: Verify Loguru logs "Redis connection verified successfully"
6. **test_get_redis_yields_client**: After `init_redis()`, `get_redis()` yields the Redis client
7. **test_get_redis_raises_before_init**: Without calling `init_redis()`, `get_redis()` raises `RuntimeError`
8. **test_close_redis_closes_client**: After `init_redis()`, `close_redis()` calls `client.close()`
9. **test_close_redis_sets_none**: After `close_redis()`, the module-level client is `None`
10. **test_close_redis_safe_without_init**: `close_redis()` does not raise when client was never initialized
11. **test_close_redis_logs_message**: Verify Loguru logs "Redis connection closed" when client exists
12. **test_lifespan_calls_init_redis**: Verify the FastAPI lifespan calls `init_redis()` on startup
13. **test_lifespan_calls_close_redis**: Verify the FastAPI lifespan calls `close_redis()` on shutdown

### Mocking Strategy
- **Redis client**: Mock `redis.asyncio.from_url` to return an `AsyncMock` with `ping()`, `close()` as `AsyncMock`
- **Settings**: Use `os.environ.setdefault` in conftest to provide `REDIS_URL` before module import
- **Loguru**: Capture logs via `loguru` sink or patch `logger.info`
- **Lifespan tests**: Mock `init_redis`, `close_redis`, `init_db`, `close_db` to avoid real connections
- **No real Redis**: All tests must pass without Redis running

### Coverage Expectation
- All 4 public exports (`get_redis`, `init_redis`, `close_redis`, `_redis_client` via inspection) have tests
- Both success and error paths for `get_redis()` are tested
- Both `init_redis()` and `close_redis()` are tested
- Lifespan integration is tested

---

## References
- roadmap.md — Phase 2, S2.2
- design.md, requirements.md
- `redis.asyncio` docs (redis-py >= 4.5)
- S1.3 `backend/app/core/config.py` — `settings.REDIS_URL`
- S1.4 `backend/app/main.py` — lifespan hooks
- S2.1 `backend/app/db/database.py` — pattern reference for init/close hooks
- MEMORY.md — gotcha: `aioredis` broken on Python 3.11+, use `redis>=4.5` with `redis.asyncio`
