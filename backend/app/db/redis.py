"""S2.2 — Async Redis Client.

Provides: get_redis(), init_redis(), close_redis().
Uses redis.asyncio (NOT deprecated aioredis).
Lazy init — no import-time connections.
"""

from typing import AsyncGenerator

import redis.asyncio as redis_asyncio
from loguru import logger

from backend.app.core.config import settings

# ── FR-1: Module-level client (lazily created by init_redis) ─────────────────
_redis_client: redis_asyncio.Redis | None = None


# ── FR-2: get_redis() FastAPI Dependency ─────────────────────────────────────
async def get_redis() -> AsyncGenerator[redis_asyncio.Redis, None]:
    """Yield the async Redis client. Raises RuntimeError if init_redis() not called."""
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized. Call init_redis() first.")
    yield _redis_client


# ── FR-3: init_redis() Startup Hook ─────────────────────────────────────────
async def init_redis() -> None:
    """Create Redis client from settings, ping to verify connectivity."""
    global _redis_client
    _redis_client = redis_asyncio.from_url(settings.REDIS_URL, decode_responses=True)
    await _redis_client.ping()
    logger.info("Redis connection verified successfully")


# ── FR-4: close_redis() Shutdown Hook ────────────────────────────────────────
async def close_redis() -> None:
    """Close Redis connection pool. Safe to call even if never initialized."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")
