"""
app/db/redis.py — Redis FastAPI dependency (mirrors get_db())

What it does:
    Provides get_redis() — an async generator that yields a connected
    redis.asyncio.Redis client and ensures it is closed after use.

Integration:
    get_redis() ← api/webhooks.py  (Depends — session state machine)
               ← services/drug_lookup.py (Day 2 — drug cache)
"""

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis

from app.core.config import settings


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    """Yield a request-scoped async Redis client via FastAPI Depends().

    Lifecycle per request:
        1. Creates a Redis client from settings.redis_url.
        2. Yields it to the route handler.
        3. Closes the client via aclose() in the finally block.

    Example usage in a route:
        from fastapi import Depends
        from redis.asyncio import Redis
        from app.db.redis import get_redis

        @router.post("/webhook/whatsapp")
        async def webhook(r: Redis = Depends(get_redis)):
            await r.set("key", "value")
    """
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()
