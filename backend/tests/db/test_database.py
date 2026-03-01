"""Tests for S2.1 — Async SQLAlchemy Engine (backend/app/db/database.py).

TDD Red phase: all 15 tests written before implementation.
All tests run without a real PostgreSQL database.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import DeclarativeBase


def _make_engine_mock_with_connect():
    """Create a mock engine whose connect() returns a proper async context manager."""
    mock_conn = AsyncMock()
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()

    @asynccontextmanager
    async def _connect():
        yield mock_conn

    mock_engine.connect = _connect
    return mock_engine, mock_conn


# ---------------------------------------------------------------------------
# FR-1: Async Engine
# ---------------------------------------------------------------------------


class TestAsyncEngine:
    """Verify engine is an AsyncEngine with correct pool configuration."""

    def test_engine_is_async_engine(self):
        from backend.app.db.database import engine

        assert isinstance(engine, AsyncEngine)

    def test_engine_pool_size(self):
        from backend.app.db.database import engine

        assert engine.pool.size() == 5

    def test_engine_max_overflow(self):
        from backend.app.db.database import engine

        assert engine.pool._max_overflow == 10

    def test_engine_uses_database_url(self):
        from backend.app.core.config import settings
        from backend.app.db.database import engine

        # SQLAlchemy obscures passwords in str(url), so use render_as_string
        assert engine.url.render_as_string(hide_password=False) == settings.DATABASE_URL


# ---------------------------------------------------------------------------
# FR-2: Async Session Factory
# ---------------------------------------------------------------------------


class TestAsyncSessionFactory:
    """Verify AsyncSessionLocal produces sessions with correct config."""

    def test_async_session_local_produces_async_session(self):
        from backend.app.db.database import AsyncSessionLocal

        session = AsyncSessionLocal()
        assert isinstance(session, AsyncSession)
        # Clean up — close the session synchronously via the sync_session
        # (no DB connection was actually opened)

    def test_session_expire_on_commit_false(self):
        from backend.app.db.database import AsyncSessionLocal

        # The session factory should have expire_on_commit=False
        session = AsyncSessionLocal()
        assert session.sync_session.expire_on_commit is False


# ---------------------------------------------------------------------------
# FR-3: Declarative Base
# ---------------------------------------------------------------------------


class TestDeclarativeBase:
    """Verify Base is a proper DeclarativeBase subclass."""

    def test_base_is_declarative_base(self):
        from backend.app.db.database import Base

        assert issubclass(Base, DeclarativeBase)


# ---------------------------------------------------------------------------
# FR-4: get_db() FastAPI Dependency
# ---------------------------------------------------------------------------


class TestGetDb:
    """Verify get_db() yields a session and handles commit/rollback/close."""

    @pytest.mark.asyncio
    async def test_get_db_yields_session(self):
        from backend.app.db.database import get_db

        mock_session = AsyncMock(spec=AsyncSession)
        with patch("backend.app.db.database.AsyncSessionLocal", return_value=mock_session):
            gen = get_db()
            session = await gen.__anext__()
            assert session is mock_session
            # Clean up generator
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass

    @pytest.mark.asyncio
    async def test_get_db_commits_on_success(self):
        from backend.app.db.database import get_db

        mock_session = AsyncMock(spec=AsyncSession)
        with patch("backend.app.db.database.AsyncSessionLocal", return_value=mock_session):
            gen = get_db()
            await gen.__anext__()
            # Signal successful completion
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass
            mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_rollback_on_exception(self):
        from backend.app.db.database import get_db

        mock_session = AsyncMock(spec=AsyncSession)
        with patch("backend.app.db.database.AsyncSessionLocal", return_value=mock_session):
            gen = get_db()
            await gen.__anext__()
            # Signal exception
            with pytest.raises(ValueError, match="test error"):
                await gen.athrow(ValueError("test error"))
            mock_session.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_db_closes_session(self):
        from backend.app.db.database import get_db

        mock_session = AsyncMock(spec=AsyncSession)
        with patch("backend.app.db.database.AsyncSessionLocal", return_value=mock_session):
            # Success path
            gen = get_db()
            await gen.__anext__()
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass
            mock_session.close.assert_awaited_once()

        # Error path — session should also close
        mock_session_err = AsyncMock(spec=AsyncSession)
        with patch("backend.app.db.database.AsyncSessionLocal", return_value=mock_session_err):
            gen = get_db()
            await gen.__anext__()
            with pytest.raises(RuntimeError):
                await gen.athrow(RuntimeError("boom"))
            mock_session_err.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# FR-5: Startup & Shutdown Hooks
# ---------------------------------------------------------------------------


class TestStartupShutdown:
    """Verify init_db() and close_db() work correctly."""

    @pytest.mark.asyncio
    async def test_init_db_executes_select_1(self):
        from backend.app.db import database

        mock_engine, mock_conn = _make_engine_mock_with_connect()

        with patch.object(database, "engine", mock_engine):
            await database.init_db()

        mock_conn.execute.assert_awaited_once()
        # Verify the SQL text contains SELECT 1
        call_args = mock_conn.execute.call_args
        sql_text = str(call_args[0][0])
        assert "SELECT 1" in sql_text or "select 1" in sql_text

    @pytest.mark.asyncio
    async def test_init_db_logs_success(self):
        from backend.app.db import database

        mock_engine, mock_conn = _make_engine_mock_with_connect()

        with (
            patch.object(database, "engine", mock_engine),
            patch("backend.app.db.database.logger") as mock_logger,
        ):
            await database.init_db()

        # Verify at least one info log was called with a success-related message
        mock_logger.info.assert_called()
        log_message = str(mock_logger.info.call_args)
        assert "connect" in log_message.lower() or "database" in log_message.lower()

    @pytest.mark.asyncio
    async def test_close_db_disposes_engine(self):
        from backend.app.db import database

        mock_engine = AsyncMock()

        with patch.object(database, "engine", mock_engine):
            await database.close_db()

        mock_engine.dispose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_db_safe_without_init(self):
        """close_db() should not raise even if the engine was never used."""
        from backend.app.db import database

        mock_engine = AsyncMock()

        with patch.object(database, "engine", mock_engine):
            # Should not raise
            await database.close_db()
