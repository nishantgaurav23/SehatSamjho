"""Alembic environment configuration for async SQLAlchemy.

This module configures how Alembic connects to the database and discovers
model metadata for autogenerate support. Uses asyncpg via async_engine_from_config
to match the app's async database layer.

Integration: reads DATABASE_URL from app settings, imports Base metadata from
db/models.py so that `alembic revision --autogenerate` detects schema changes.
"""

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Add backend/ to sys.path so app imports resolve when running alembic from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.db.models import Base  # noqa: E402

# Alembic Config object — provides access to values in alembic.ini
config = context.config

# Override sqlalchemy.url with value from app settings so we never hardcode creds
config.set_main_option("sqlalchemy.url", settings.database_url)

# Configure Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate — Alembic diffs this against the live DB schema
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection needed).

    Generates SQL script output instead of executing against a database.
    Useful for reviewing migrations or applying to production manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations against an active connection."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations via a sync connection wrapper.

    asyncpg requires the engine to be created asynchronously; Alembic's
    run_sync helper bridges the async engine to Alembic's synchronous API.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # no connection pooling during migrations
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migration mode (live DB connection)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
