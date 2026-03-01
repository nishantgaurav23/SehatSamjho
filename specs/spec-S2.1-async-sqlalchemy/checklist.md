# Checklist — Spec S2.1: Async SQLAlchemy Engine

## Phase 1: Setup & Dependencies
- [x] Verify S1.3 (pydantic-settings config) is implemented and tests pass
- [x] Verify S1.4 (FastAPI app factory) is implemented and tests pass
- [x] Create target file: `backend/app/db/database.py`
- [x] Confirm `sqlalchemy[asyncio]` and `asyncpg` are in pyproject.toml (from S1.1)

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/db/test_database.py`
- [x] Write test_engine_is_async_engine
- [x] Write test_engine_pool_size
- [x] Write test_engine_max_overflow
- [x] Write test_engine_uses_database_url
- [x] Write test_async_session_local_produces_async_session
- [x] Write test_session_expire_on_commit_false
- [x] Write test_base_is_declarative_base
- [x] Write test_get_db_yields_session
- [x] Write test_get_db_commits_on_success
- [x] Write test_get_db_rollback_on_exception
- [x] Write test_get_db_closes_session
- [x] Write test_init_db_executes_select_1
- [x] Write test_init_db_logs_success
- [x] Write test_close_db_disposes_engine
- [x] Write test_close_db_safe_without_init
- [x] Run make local-test — expect failures (Red)

## Phase 3: Implementation
- [x] Implement FR-1: create_async_engine with pool_size=5, max_overflow=10
- [x] Implement FR-2: AsyncSessionLocal (async_sessionmaker, expire_on_commit=False)
- [x] Implement FR-3: Base (DeclarativeBase subclass)
- [x] Implement FR-4: get_db() async generator (yield session, commit/rollback/close)
- [x] Implement FR-5: init_db() (SELECT 1 connectivity check + log) and close_db() (engine.dispose())
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Wire init_db() and close_db() into main.py lifespan (startup/shutdown)
- [x] Verify /health still works after lifespan changes
- [x] Run make local-lint
- [x] Run full test suite: make local-test

## Phase 5: Verification
- [x] All tangible outcomes checked
- [x] No hardcoded secrets (DATABASE_URL from settings only)
- [x] Logging includes context where applicable
- [x] Update roadmap.md status: spec-written -> done
