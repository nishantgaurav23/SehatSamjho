"""Tests for S2.2 — Async Redis Client.

Red → Green → Refactor.
13 tests covering init_redis, get_redis, close_redis, and lifespan wiring.
All tests mock Redis — no real Redis server needed.
"""

import os

# Ensure env vars are set before any app imports (module-level Settings())
_TEST_ENV = {
    "OPENAI_API_KEY": "sk-test-openai",
    "ANTHROPIC_API_KEY": "sk-ant-test-anthropic",
    "TWILIO_ACCOUNT_SID": "ACtest1234567890",
    "TWILIO_AUTH_TOKEN": "test-twilio-token",
    "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
    "BHASHINI_API_KEY": "test-bhashini-key",
    "BHASHINI_USER_ID": "test-bhashini-user",
    "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/testdb",
    "REDIS_URL": "redis://localhost:6379/0",
}
for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)

import pytest  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402
from loguru import logger  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_mock_redis():
    """Create a mock Redis client with async ping() and close()."""
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.close = AsyncMock()
    return mock_client


def _reset_redis_module():
    """Reset module-level _redis_client to None for test isolation."""
    import backend.app.db.redis as redis_mod

    redis_mod._redis_client = None


# ── Test 1: init_redis creates client ────────────────────────────────────────


@pytest.mark.asyncio
async def test_init_redis_creates_client():
    """After calling init_redis(), the module-level client should not be None."""
    _reset_redis_module()
    mock_client = _make_mock_redis()

    with patch("backend.app.db.redis.redis_asyncio.from_url", return_value=mock_client):
        from backend.app.db.redis import init_redis
        import backend.app.db.redis as redis_mod

        await init_redis()
        assert redis_mod._redis_client is not None

    _reset_redis_module()


# ── Test 2: init_redis calls ping ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_init_redis_calls_ping():
    """Verify that ping() is called on the client during init_redis()."""
    _reset_redis_module()
    mock_client = _make_mock_redis()

    with patch("backend.app.db.redis.redis_asyncio.from_url", return_value=mock_client):
        from backend.app.db.redis import init_redis

        await init_redis()
        mock_client.ping.assert_awaited_once()

    _reset_redis_module()


# ── Test 3: init_redis uses REDIS_URL ────────────────────────────────────────


@pytest.mark.asyncio
async def test_init_redis_uses_redis_url():
    """Verify from_url() is called with settings.REDIS_URL."""
    _reset_redis_module()
    mock_client = _make_mock_redis()

    with patch(
        "backend.app.db.redis.redis_asyncio.from_url", return_value=mock_client
    ) as mock_from:
        from backend.app.db.redis import init_redis
        from backend.app.core.config import settings

        await init_redis()
        mock_from.assert_called_once()
        call_args = mock_from.call_args
        assert call_args[0][0] == settings.REDIS_URL

    _reset_redis_module()


# ── Test 4: init_redis decode_responses ──────────────────────────────────────


@pytest.mark.asyncio
async def test_init_redis_decode_responses():
    """Verify from_url() is called with decode_responses=True."""
    _reset_redis_module()
    mock_client = _make_mock_redis()

    with patch(
        "backend.app.db.redis.redis_asyncio.from_url", return_value=mock_client
    ) as mock_from:
        from backend.app.db.redis import init_redis

        await init_redis()
        call_kwargs = mock_from.call_args[1]
        assert call_kwargs.get("decode_responses") is True

    _reset_redis_module()


# ── Test 5: init_redis logs success ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_init_redis_logs_success():
    """Verify Loguru logs 'Redis connection verified successfully'."""
    _reset_redis_module()
    mock_client = _make_mock_redis()
    captured: list[str] = []

    def sink(message):
        captured.append(str(message))

    handler_id = logger.add(sink, format="{message}")
    try:
        with patch("backend.app.db.redis.redis_asyncio.from_url", return_value=mock_client):
            from backend.app.db.redis import init_redis

            await init_redis()
    finally:
        logger.remove(handler_id)

    combined = "\n".join(captured)
    assert "Redis connection verified successfully" in combined

    _reset_redis_module()


# ── Test 6: get_redis yields client ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_redis_yields_client():
    """After init_redis(), get_redis() yields the Redis client."""
    _reset_redis_module()
    mock_client = _make_mock_redis()

    with patch("backend.app.db.redis.redis_asyncio.from_url", return_value=mock_client):
        from backend.app.db.redis import init_redis, get_redis

        await init_redis()

        gen = get_redis()
        client = await gen.__anext__()
        assert client is mock_client

        # Cleanup generator
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass

    _reset_redis_module()


# ── Test 7: get_redis raises before init ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_redis_raises_before_init():
    """Without calling init_redis(), get_redis() raises RuntimeError."""
    _reset_redis_module()

    from backend.app.db.redis import get_redis

    gen = get_redis()
    with pytest.raises(RuntimeError, match="Redis client not initialized"):
        await gen.__anext__()


# ── Test 8: close_redis closes client ────────────────────────────────────────


@pytest.mark.asyncio
async def test_close_redis_closes_client():
    """After init_redis(), close_redis() calls client.close()."""
    _reset_redis_module()
    mock_client = _make_mock_redis()

    with patch("backend.app.db.redis.redis_asyncio.from_url", return_value=mock_client):
        from backend.app.db.redis import init_redis, close_redis

        await init_redis()
        await close_redis()
        mock_client.close.assert_awaited_once()

    _reset_redis_module()


# ── Test 9: close_redis sets None ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_close_redis_sets_none():
    """After close_redis(), the module-level client is None."""
    _reset_redis_module()
    mock_client = _make_mock_redis()

    with patch("backend.app.db.redis.redis_asyncio.from_url", return_value=mock_client):
        from backend.app.db.redis import close_redis, init_redis
        import backend.app.db.redis as redis_mod

        await init_redis()
        await close_redis()
        assert redis_mod._redis_client is None

    _reset_redis_module()


# ── Test 10: close_redis safe without init ───────────────────────────────────


@pytest.mark.asyncio
async def test_close_redis_safe_without_init():
    """close_redis() does not raise when client was never initialized."""
    _reset_redis_module()

    from backend.app.db.redis import close_redis

    # Should not raise
    await close_redis()


# ── Test 11: close_redis logs message ────────────────────────────────────────


@pytest.mark.asyncio
async def test_close_redis_logs_message():
    """Verify Loguru logs 'Redis connection closed' when client exists."""
    _reset_redis_module()
    mock_client = _make_mock_redis()
    captured: list[str] = []

    def sink(message):
        captured.append(str(message))

    handler_id = logger.add(sink, format="{message}")
    try:
        with patch("backend.app.db.redis.redis_asyncio.from_url", return_value=mock_client):
            from backend.app.db.redis import init_redis, close_redis

            await init_redis()
            captured.clear()  # Clear init logs
            await close_redis()
    finally:
        logger.remove(handler_id)

    combined = "\n".join(captured)
    assert "Redis connection closed" in combined

    _reset_redis_module()


# ── Test 12: lifespan calls init_redis ───────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_calls_init_redis():
    """Verify the FastAPI lifespan calls init_redis() on startup."""
    with (
        patch("backend.app.main.init_db", new_callable=AsyncMock),
        patch("backend.app.main.close_db", new_callable=AsyncMock),
        patch("backend.app.main.init_redis", new_callable=AsyncMock) as mock_init_redis,
        patch("backend.app.main.close_redis", new_callable=AsyncMock),
    ):
        from backend.app.main import create_app, lifespan

        app = create_app()
        async with lifespan(app):
            pass  # startup fires

        mock_init_redis.assert_awaited_once()


# ── Test 13: lifespan calls close_redis ──────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_calls_close_redis():
    """Verify the FastAPI lifespan calls close_redis() on shutdown."""
    with (
        patch("backend.app.main.init_db", new_callable=AsyncMock),
        patch("backend.app.main.close_db", new_callable=AsyncMock),
        patch("backend.app.main.init_redis", new_callable=AsyncMock),
        patch("backend.app.main.close_redis", new_callable=AsyncMock) as mock_close_redis,
    ):
        from backend.app.main import create_app, lifespan

        app = create_app()
        async with lifespan(app):
            pass  # startup fires, shutdown fires on exit

        mock_close_redis.assert_awaited_once()
