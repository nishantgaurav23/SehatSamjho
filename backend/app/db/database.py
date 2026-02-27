"""
What this file does:
    This is the database foundation of the entire app. Every other file that talks to PostgreSQL depends on
    this one. It does three things:
        1. Creates the async database engine (the connection to PostgreSQL)
        2. Creates a session factory (a "template" for opening DB sessions)
        3. Expose get_db() - a FastAPI dependency injected into any route that needs the DB

---
database.py
    ├── Base        → inherited by db/models.py      (table definitions)
    ├── engine      → imported by alembic/env.py      (runs migrations)
    └── get_db()    → Depends() in api/webhooks.py    (logs each request)
                      Depends() in api/dashboard.py   (reads analytics)
---
Variables

  ┌───────────────────┬────────────────────┬──────────────────────────────────────────────────────────┐
  │     Variable      │        Type        │                         Purpose                          │
  ├───────────────────┼────────────────────┼──────────────────────────────────────────────────────────┤
  │ engine            │ AsyncEngine        │ One shared DB connection pool for the whole app lifetime │
  ├───────────────────┼────────────────────┼──────────────────────────────────────────────────────────┤
  │ AsyncSessionLocal │ async_sessionmaker │ Factory — call it to open a new session                  │
  ├───────────────────┼────────────────────┼──────────────────────────────────────────────────────────┤
  │ Base              │ DeclarativeBase    │ All ORM models in models.py inherit from this            │
  └───────────────────┴────────────────────┴──────────────────────────────────────────────────────────┘

Functions:

    get_db():
        - Yields one AyncSession per HTTP request
        - Commits the session if the request succeeds
        - Rolls back automatically if any exception is raised
        - Always closes the session (releases connection to pool)
        - Used as db: AsyncSession = Depends(get_db) in route handlers

---
Async SQLAlchemy engine, session factory, and FastAPI DB dependency

Provided the single entry point for all PostgreSQL interaction in SehatSamjho.
Uses the asyncpg driver (postgresql+asyncpg://) to match the fully async stack.

"""

from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────
# One engine per process, shared across all requests.
# pool_pre_ping= True silently replaces stale connections before they are
# handed to application code - handles DB restarts and network blips

engine = create_async_engine(
    settings.database_url,      # postgresql+asyncpg://... from .env
    pool_pre_ping=True,
    pool_size=5,                # persistent connections kept open between requests
    max_overflow=10,            # extra connections allowed under burst traffic
    echo=settings.debug,        # logs every SQL statement when DEBUG=True
)

# ── Session factory ───────────────────────────────────────────────────────────
# Call AsyncSessionLocal() to open a new session.
# expire_on_commit=False keeps ORM objects accessible after commit - 
# required in async SQLAlchemy because lazy loading is not supported.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# ── Declarative base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Shared base class inherited by all ORM models in db/models.py
    
    Alembic reads Base.metadata in alembic/env.py to detect schema changes
    and autogenerate migration scripts via `make makemigrations`.
    """

# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped async DB session via FastAPI Depends().
    
    Lifecycle per request:
        1. Opens a new AsyncSession from AsyncSessionLocal.
        2. Yields it to the route handler.
        3. Commits on clean exit (no exception).
        4. Rolls back on any unhandled exception, then re-raises.
        5. Always closes the session in the finally block.

    Args:
        None - called automatically by FastAPI's dependency injection.

    Yields:
        AsyncSession: A SQLAlchemy async session for the current request.

    Raises:
        Exception: Re-raises any exception from the route handler after
                   rolling back, so FastAPI's error handlers receive it normally.

    Example usage in a route:
        from fastapi import Depends
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.db.database import get_db

        @router.post("/webhook/whatsapp")
        async def webhook(db: AsyncSession = Depends(get_db)):
            db.add(TranslationLog(...))
            # commit happens automatically when the request completes
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("DB session rolled back due to unhandled exception")
            raise
        finally:
            await session.close()