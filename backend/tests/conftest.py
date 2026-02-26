"""
Shared pytest fixtures for SehatSamjho test suite.

Provides:
    - anyio_backend      : tells pytest-asyncio to use asyncio
    - db_session         : async SQLAlchemy session, rolled back after each test
    - event_loop         : session-scoped loop shared by all tests and fixtures
    - reset_connection_pool : disposes the engine pool before each test
    - cleanup_engine     : disposes the engine pool at session end (before loop closes)

All tests run against a real PostgreSQL instance (start with `make services`).
Set DATABASE_URL in .env before running tests.

Event-loop strategy
-------------------
pytest-asyncio 0.24 gives each *test function* its own event loop by default.
asyncpg binds connections to the loop they were created on, so connections pooled
in test N cannot be safely reused in test N+1 (different loop) when pool_pre_ping
is enabled — this raises "Future attached to a different loop".

Fix: a session-scoped `event_loop` fixture forces all tests and async fixtures to
share one loop.  This is deprecated in pytest-asyncio 0.24 (one warning per run)
but is the only correct approach until 0.25+ adds asyncio_default_test_loop_scope.

Teardown order (LIFO within session scope, defined order in this file):
    1. cleanup_engine  → await engine.dispose()  (loop still open)
    2. event_loop      → loop.close()
This ensures all asyncpg connections are closed before the loop shuts down,
preventing "Event loop is closed" GC warnings at the end of the test session.
"""

import asyncio
from pathlib import Path

from dotenv import load_dotenv

# Load .env before importing any app module — config.py reads env vars at import time.
# conftest.py is at backend/tests/ → parents[2] = project root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import pytest  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.database import AsyncSessionLocal, engine  # noqa: E402


@pytest.fixture
def anyio_backend():
    """Tell pytest-asyncio to use the asyncio event loop."""
    return "asyncio"


@pytest.fixture
async def db_session() -> AsyncSession:
    """Yield a real async DB session, rolled back after every test.

    Using rollback instead of commit means every test starts with a
    clean DB state — no leftover rows between tests.

    Yields:
        AsyncSession: Live session connected to the test database.
    """
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()  # undo anything the test wrote


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop shared by all tests and async fixtures.

    Forces every test function onto one loop so asyncpg connections pooled
    in one test can be safely reused (or disposed) in the next test.
    Deprecated in pytest-asyncio 0.24 — produces one warning per run.
    Required until pytest-asyncio 0.25+ which adds asyncio_default_test_loop_scope.

    Teardown runs engine.dispose() before loop.close() using
    loop.run_until_complete() — this is the only safe way to guarantee all
    asyncpg connections are closed while the loop is still active, preventing
    "RuntimeError: Event loop is closed" GC warnings.
    """
    loop = asyncio.new_event_loop()
    yield loop
    loop.run_until_complete(engine.dispose())
    loop.close()


@pytest.fixture(autouse=True)
async def reset_connection_pool():
    """Dispose the engine connection pool before each test.

    Ensures no connection from a previous test enters the next test's
    execution context.  With pool_pre_ping=True, a stale pooled connection
    would trigger a ping on what might be a different event loop, raising
    "Future attached to a different loop".
    """
    await engine.dispose()
    yield
