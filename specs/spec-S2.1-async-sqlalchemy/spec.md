# Spec S2.1 — Async SQLAlchemy Engine

## Overview
Sets up the async SQLAlchemy engine, session factory, declarative base, and a FastAPI dependency (`get_db()`) for injecting async database sessions into endpoints. Uses `create_async_engine` with `asyncpg` driver. Connection pool tuned for the t3.micro target: `pool_size=5`, `max_overflow=10`. The engine is created once at module level (lazy) and the session factory wraps it. The lifespan (S1.4) will call startup/shutdown hooks to verify connectivity and dispose the engine cleanly.

## Dependencies
- **S1.3** (pydantic-settings config) — provides `settings.DATABASE_URL`
- **S1.4** (FastAPI app factory) — lifespan hooks for startup/shutdown integration

## Target Location
`backend/app/db/database.py`

---

## Functional Requirements

### FR-1: Async Engine Creation
- **What**: Create an async SQLAlchemy engine using `create_async_engine` with the `DATABASE_URL` from settings.
- **Inputs**: `settings.DATABASE_URL` (string, `postgresql+asyncpg://...` format)
- **Outputs**: A `sqlalchemy.ext.asyncio.AsyncEngine` instance
- **Config**: `pool_size=5`, `max_overflow=10`, `echo=False` (production default)
- **Edge cases**: Invalid DATABASE_URL should raise at engine creation or first connect, not silently fail

### FR-2: Async Session Factory
- **What**: Create an `async_sessionmaker` bound to the engine. Sessions should not auto-commit or auto-flush (explicit control).
- **Inputs**: The async engine from FR-1
- **Outputs**: `AsyncSessionLocal` — an `async_sessionmaker[AsyncSession]` callable
- **Config**: `expire_on_commit=False` (prevents lazy-load issues after commit in async context)

### FR-3: Declarative Base
- **What**: Export a `Base` class (`DeclarativeBase` subclass) for all ORM models to inherit from.
- **Inputs**: None
- **Outputs**: `Base` class usable as `class MyModel(Base): ...`
- **Edge cases**: Must be importable from `backend.app.db.database` by model modules (S2.3)

### FR-4: `get_db()` FastAPI Dependency
- **What**: An async generator that yields an `AsyncSession`, commits on success, rolls back on exception, and always closes.
- **Inputs**: None (called by FastAPI dependency injection)
- **Outputs**: Yields `AsyncSession` to the endpoint
- **Behavior**:
  1. Open session via `AsyncSessionLocal()`
  2. `yield session` to endpoint
  3. On success: `await session.commit()`
  4. On exception: `await session.rollback()`, then re-raise
  5. Finally: `await session.close()`
- **Edge cases**: Must handle the case where the session is already closed or the connection pool is exhausted (SQLAlchemy raises `TimeoutError`)

### FR-5: Startup & Shutdown Hooks
- **What**: Provide `init_db()` and `close_db()` async functions for the lifespan to call.
- **`init_db()`**: Execute a simple `SELECT 1` via the engine to verify connectivity. Log success or raise on failure.
- **`close_db()`**: Call `engine.dispose()` to cleanly release all pooled connections.
- **Outputs**: `init_db()` returns `None` (logs on success, raises on connection failure). `close_db()` returns `None`.
- **Edge cases**: `close_db()` should be safe to call even if `init_db()` was never called or failed.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `from backend.app.db.database import engine` returns an `AsyncEngine` with pool_size=5, max_overflow=10
- [ ] **Outcome 2**: `from backend.app.db.database import AsyncSessionLocal` produces `AsyncSession` instances
- [ ] **Outcome 3**: `from backend.app.db.database import Base` is a valid DeclarativeBase for ORM model inheritance
- [ ] **Outcome 4**: `get_db()` yields a session, commits on success, rolls back on error, always closes
- [ ] **Outcome 5**: `init_db()` runs `SELECT 1` to verify DB connectivity and logs success
- [ ] **Outcome 6**: `close_db()` disposes the engine and is safe to call unconditionally

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_engine_is_async_engine**: Verify `engine` is an instance of `AsyncEngine`
2. **test_engine_pool_size**: Verify `engine.pool.size() == 5`
3. **test_engine_max_overflow**: Verify `engine.pool._max_overflow == 10`
4. **test_engine_uses_database_url**: Verify engine URL matches `settings.DATABASE_URL`
5. **test_async_session_local_produces_async_session**: Call `AsyncSessionLocal()` and verify it yields `AsyncSession`
6. **test_session_expire_on_commit_false**: Verify session factory has `expire_on_commit=False`
7. **test_base_is_declarative_base**: Verify `Base` is a subclass of `DeclarativeBase`
8. **test_get_db_yields_session**: Call `get_db()`, verify it yields an `AsyncSession`
9. **test_get_db_commits_on_success**: Verify session.commit() is called when no exception
10. **test_get_db_rollback_on_exception**: Verify session.rollback() is called on exception, exception re-raised
11. **test_get_db_closes_session**: Verify session.close() is always called (success and failure paths)
12. **test_init_db_executes_select_1**: Mock engine.connect(), verify `SELECT 1` is executed
13. **test_init_db_logs_success**: Verify Loguru logs a success message on connectivity check
14. **test_close_db_disposes_engine**: Verify `engine.dispose()` is called
15. **test_close_db_safe_without_init**: Verify `close_db()` doesn't raise even if engine was never used

### Mocking Strategy
- **Database engine**: Use `unittest.mock.AsyncMock` to mock the engine's `connect()`, `begin()`, and `dispose()` methods
- **AsyncSession**: Mock `AsyncSessionLocal` to return a mock `AsyncSession` with `commit()`, `rollback()`, `close()` as `AsyncMock`
- **Settings**: Patch `settings.DATABASE_URL` if needed (but module-level engine reads it at import time, so use env var override in conftest)
- **No real database**: All tests must pass without PostgreSQL running

### Coverage Expectation
- All 5 public exports (`engine`, `AsyncSessionLocal`, `Base`, `get_db`, `init_db`, `close_db`) have at least one test
- Both success and failure paths in `get_db()` are tested
- Both `init_db()` and `close_db()` are tested

---

## References
- roadmap.md — Phase 2, S2.1
- design.md, requirements.md
- SQLAlchemy 2.0 async docs: `create_async_engine`, `async_sessionmaker`, `DeclarativeBase`
- S1.3 `backend/app/core/config.py` — `settings.DATABASE_URL`
- S1.4 `backend/app/main.py` — lifespan hooks
