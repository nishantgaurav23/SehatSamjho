"""S2.1 — Async SQLAlchemy Engine.

Provides: engine, AsyncSessionLocal, Base, get_db(), init_db(), close_db().
Connection pool tuned for t3.micro: pool_size=5, max_overflow=10.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from loguru import logger

from backend.app.core.config import settings

# ── FR-1: Async Engine ───────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

# ── FR-2: Async Session Factory ──────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── FR-3: Declarative Base ───────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Base class for all ORM models."""


# ── FR-4: get_db() FastAPI Dependency ────────────────────────────────────────
async def get_db():
    """Yield an async session; commit on success, rollback on error, always close."""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ── FR-5: Startup & Shutdown Hooks ───────────────────────────────────────────
async def init_db() -> None:
    """Verify database connectivity by executing SELECT 1."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection verified successfully")


async def close_db() -> None:
    """Dispose the engine, releasing all pooled connections."""
    await engine.dispose()
    logger.info("Database engine disposed")
