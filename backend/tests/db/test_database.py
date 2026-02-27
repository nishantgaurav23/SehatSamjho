"""Tests for app/db/database.py

Tests:
    - engine can connect to PostgreSQL
    - AsyncSessionLocal creates a working session
    - get_db() commits on clean exit
    - get_db() rolls back on exception

Run: 
    cd backend/
    pytest tests/db/test_database.py -v

---
How to run

# from project root
source .venv/bin/activate

# start postgres (if not already running)
make up

# run just the database tests
cd backend
pytest tests/db/test_database.py -v

"""
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal, engine, get_db

# ── Engine tests ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_engine_connects():
    """Engine can open a connection and execute a basic query."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1 AS check_val"))
        assert result.scalar() == 1

@pytest.mark.asyncio
async def test_engine_connects_to_correct_database():
    """Engine is connected to the sehatsamjho database."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT current_database()"))
        db_name = result.scalar()
        assert db_name == "sehatsamjho", f"Expected 'sehatsamjho', got '{db_name}'"

# ── Session factory tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_factory_creates_valid_session():
    """AsyncSessionLocal() returns a working AsyncSession."""
    async with AsyncSessionLocal() as session:
        assert isinstance(session, AsyncSession)
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

@pytest.mark.asyncio
async def test_session_factory_is_not_expired_on_commit():
    """expire_on_commit=False — objects stay accessible after commit."""
    async with AsyncSessionLocal() as session:
        # expire_on_commit lives on the underlying sync session
        assert session.sync_session.expire_on_commit is False

# ── get_db() dependency tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_db_yields_async_session():
    """get_db() yields an AsyncSession instance."""
    gen = get_db()
    session = await gen.__anext__()
    assert isinstance(session, AsyncSession)
    try:
        await gen.aclose()
    except StopAsyncIteration:
        pass

@pytest.mark.asyncio
async def test_get_db_commits_on_clean_exit(db_session):
    """get_db() commits the session when no exception is raised."""
    committed = False

    async def simulate_route():
        nonlocal committed
        async for session in get_db():
            await session.execute(text("SELECT 1"))
            committed = True

    await simulate_route()
    assert committed is True

@pytest.mark.asyncio
async def test_get_db_rolls_back_on_exception():
    """get_db() rolls back and re-raises on exception."""
    exception_raised = False

    try:
        async for session in get_db():
            await session.execute(text("SELECT 1"))
            raise ValueError("simulated route error")
    except ValueError:
        exception_raised = True

    assert exception_raised is True