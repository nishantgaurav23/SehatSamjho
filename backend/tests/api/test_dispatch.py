"""S4.2 — Dispatch tests.

20 tests covering _dispatch(), _save_session(), _delete_session(), _load_session(),
session key format, routing by SessionStatus, handler stubs, webhook integration,
and logging with request_id.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# Ensure test env vars are set BEFORE importing modules that read settings
# ---------------------------------------------------------------------------
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
    "S3_BUCKET": "test-bucket",
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
}
for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from loguru import logger  # noqa: E402

from backend.app.api.webhooks import (  # noqa: E402
    SESSION_KEY_PREFIX,
    SESSION_TTL_SECONDS,
    _delete_session,
    _dispatch,
    _handle_image_state,
    _handle_language_state,
    _handle_welcome_state,
    _save_session,
)
from backend.app.core.security import validate_twilio_signature  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.models.schemas import (  # noqa: E402
    SessionState,
    SessionStatus,
    WebhookPayload,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PHONE = "whatsapp:+919876543210"


def _make_payload(**overrides) -> WebhookPayload:
    defaults = {"from_number": PHONE, "body": "Hello", "num_media": 0}
    defaults.update(overrides)
    return WebhookPayload(**defaults)


def _make_session(status: SessionStatus = SessionStatus.WAITING_FOR_LANGUAGE) -> SessionState:
    return SessionState(
        status=status,
        language_code=None,
        language_name=None,
        request_id=str(uuid.uuid4()),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _mock_redis(get_value=None) -> AsyncMock:
    """Create a mock Redis client with configurable get() return value."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=get_value)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_redis_client():
    """A mock Redis client for dependency override."""
    return _mock_redis(get_value=None)


@pytest.fixture()
def app(mock_redis_client):
    """Create a test app with HMAC and Redis overridden."""
    from backend.app.db.redis import get_redis

    app = create_app()
    app.dependency_overrides[validate_twilio_signature] = lambda: None

    async def _override_redis():
        yield mock_redis_client

    app.dependency_overrides[get_redis] = _override_redis
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _form_data(**overrides) -> dict:
    data = {
        "From": PHONE,
        "Body": "Hello doctor",
        "NumMedia": "0",
    }
    data.update(overrides)
    return data


# ===========================================================================
# Session Loading (tests 1–4)
# ===========================================================================


@pytest.mark.asyncio
async def test_dispatch_new_user_no_session():
    """No Redis key → _dispatch() routes to welcome handler."""
    redis = _mock_redis(get_value=None)
    payload = _make_payload()

    with patch(
        "backend.app.api.webhooks._handle_welcome_state", new_callable=AsyncMock
    ) as mock_welcome:
        await _dispatch(payload, "req-123", redis)
        mock_welcome.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_loads_existing_session():
    """Valid session JSON in Redis → correct handler called."""
    session = _make_session(SessionStatus.WAITING_FOR_LANGUAGE)
    redis = _mock_redis(get_value=session.model_dump_json())
    payload = _make_payload()

    with patch(
        "backend.app.api.webhooks._handle_language_state", new_callable=AsyncMock
    ) as mock_lang:
        await _dispatch(payload, "req-123", redis)
        mock_lang.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_corrupted_session_json():
    """Invalid JSON in Redis → deletes key, routes to welcome."""
    redis = _mock_redis(get_value="not-valid-json{{{")
    payload = _make_payload()

    with patch(
        "backend.app.api.webhooks._handle_welcome_state", new_callable=AsyncMock
    ) as mock_welcome:
        await _dispatch(payload, "req-123", redis)
        mock_welcome.assert_awaited_once()
        redis.delete.assert_awaited_once_with(f"{SESSION_KEY_PREFIX}{PHONE}")


@pytest.mark.asyncio
async def test_dispatch_redis_key_format():
    """Session key is session:{from_number}."""
    redis = _mock_redis(get_value=None)
    payload = _make_payload()

    with patch("backend.app.api.webhooks._handle_welcome_state", new_callable=AsyncMock):
        await _dispatch(payload, "req-123", redis)
        redis.get.assert_awaited_once_with(f"session:{PHONE}")


# ===========================================================================
# Routing (tests 5–8)
# ===========================================================================


@pytest.mark.asyncio
async def test_dispatch_routes_waiting_for_language():
    """Session with WAITING_FOR_LANGUAGE → _handle_language_state()."""
    session = _make_session(SessionStatus.WAITING_FOR_LANGUAGE)
    redis = _mock_redis(get_value=session.model_dump_json())
    payload = _make_payload()

    with patch(
        "backend.app.api.webhooks._handle_language_state", new_callable=AsyncMock
    ) as mock_lang:
        await _dispatch(payload, "req-123", redis)
        mock_lang.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_routes_waiting_for_image():
    """Session with WAITING_FOR_IMAGE → _handle_image_state()."""
    session = _make_session(SessionStatus.WAITING_FOR_IMAGE)
    redis = _mock_redis(get_value=session.model_dump_json())
    payload = _make_payload()

    with patch("backend.app.api.webhooks._handle_image_state", new_callable=AsyncMock) as mock_img:
        await _dispatch(payload, "req-123", redis)
        mock_img.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_routes_processing():
    """Session with PROCESSING → sends 'still processing' message."""
    session = _make_session(SessionStatus.PROCESSING)
    redis = _mock_redis(get_value=session.model_dump_json())
    payload = _make_payload()

    with patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock) as mock_send:
        await _dispatch(payload, "req-123", redis)
        mock_send.assert_awaited_once()
        args = mock_send.call_args[0]
        assert args[0] == PHONE
        assert "processing" in args[1].lower() or "wait" in args[1].lower()


@pytest.mark.asyncio
async def test_dispatch_routes_unknown_status():
    """Unknown status → deletes session, routes to welcome."""
    # Manually craft JSON with a bogus status to simulate an unknown value
    session_json = json.dumps(
        {
            "status": "some_bogus_status",
            "language_code": None,
            "language_name": None,
            "request_id": "r-1",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    redis = _mock_redis(get_value=session_json)
    payload = _make_payload()

    with patch(
        "backend.app.api.webhooks._handle_welcome_state", new_callable=AsyncMock
    ) as mock_welcome:
        await _dispatch(payload, "req-123", redis)
        mock_welcome.assert_awaited_once()
        redis.delete.assert_awaited()


# ===========================================================================
# Session Persistence (tests 9–13)
# ===========================================================================


@pytest.mark.asyncio
async def test_save_session_stores_json():
    """_save_session() writes valid JSON to Redis."""
    redis = _mock_redis()
    session = _make_session()

    await _save_session(PHONE, session, redis)

    redis.set.assert_awaited_once()
    call_args = redis.set.call_args
    stored_json = call_args[0][1]
    # Should be valid JSON that round-trips to SessionState
    parsed = SessionState.model_validate_json(stored_json)
    assert parsed.status == session.status


@pytest.mark.asyncio
async def test_save_session_sets_ttl():
    """_save_session() sets 30-minute (1800s) TTL."""
    redis = _mock_redis()
    session = _make_session()

    await _save_session(PHONE, session, redis)

    call_kwargs = redis.set.call_args[1]
    assert call_kwargs.get("ex") == SESSION_TTL_SECONDS


@pytest.mark.asyncio
async def test_save_session_overwrites_existing():
    """_save_session() replaces prior session."""
    redis = _mock_redis()
    session1 = _make_session(SessionStatus.WAITING_FOR_LANGUAGE)
    session2 = _make_session(SessionStatus.WAITING_FOR_IMAGE)

    await _save_session(PHONE, session1, redis)
    await _save_session(PHONE, session2, redis)

    assert redis.set.await_count == 2
    # Second call should have the updated session
    second_call_json = redis.set.call_args_list[1][0][1]
    parsed = SessionState.model_validate_json(second_call_json)
    assert parsed.status == SessionStatus.WAITING_FOR_IMAGE


@pytest.mark.asyncio
async def test_delete_session_removes_key():
    """_delete_session() calls Redis DEL on session key."""
    redis = _mock_redis()

    await _delete_session(PHONE, redis)

    redis.delete.assert_awaited_once_with(f"{SESSION_KEY_PREFIX}{PHONE}")


@pytest.mark.asyncio
async def test_delete_session_nonexistent_key_no_error():
    """_delete_session() on missing key does not raise."""
    redis = _mock_redis()
    redis.delete = AsyncMock(return_value=0)  # Redis returns 0 for non-existent keys

    await _delete_session(PHONE, redis)  # Should not raise


# ===========================================================================
# Webhook Integration (tests 14–15)
# ===========================================================================


@pytest.mark.asyncio
async def test_webhook_calls_dispatch(app):
    """POST to /webhook/whatsapp with valid payload triggers _dispatch()."""
    with (
        patch("backend.app.api.webhooks._dispatch", new_callable=AsyncMock) as mock_dispatch,
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/webhook/whatsapp", data=_form_data())
        assert resp.status_code == 200
        mock_dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_returns_twiml_after_dispatch(app):
    """Endpoint still returns <Response/> after dispatch."""
    with (
        patch("backend.app.api.webhooks._dispatch", new_callable=AsyncMock),
        patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/webhook/whatsapp", data=_form_data())
        assert resp.status_code == 200
        assert resp.text == "<Response/>"
        assert "text/xml" in resp.headers["content-type"]


# ===========================================================================
# Handler Stubs (tests 16–18)
# ===========================================================================


def test_welcome_stub_is_callable():
    """_handle_welcome_state() is an async function."""
    assert asyncio.iscoroutinefunction(_handle_welcome_state)


def test_language_stub_is_callable():
    """_handle_language_state() is an async function."""
    assert asyncio.iscoroutinefunction(_handle_language_state)


def test_image_stub_is_callable():
    """_handle_image_state() is an async function."""
    assert asyncio.iscoroutinefunction(_handle_image_state)


# ===========================================================================
# Logging (tests 19–20)
# ===========================================================================


@pytest.mark.asyncio
async def test_dispatch_logs_session_status():
    """Dispatch logs the current session status with request_id."""
    session = _make_session(SessionStatus.WAITING_FOR_IMAGE)
    redis = _mock_redis(get_value=session.model_dump_json())
    payload = _make_payload()

    log_output = StringIO()
    handler_id = logger.add(
        log_output,
        format="{extra} {message}",
        level="DEBUG",
        filter=lambda r: "request_id" in r["extra"],
    )
    try:
        with patch("backend.app.api.webhooks._handle_image_state", new_callable=AsyncMock):
            await _dispatch(payload, "req-test-456", redis)
        log_text = log_output.getvalue()
        assert "req-test-456" in log_text
        assert "waiting_for_image" in log_text.lower() or "WAITING_FOR_IMAGE" in log_text
    finally:
        logger.remove(handler_id)


@pytest.mark.asyncio
async def test_dispatch_logs_new_user():
    """Dispatch logs 'New user' for sessions that don't exist."""
    redis = _mock_redis(get_value=None)
    payload = _make_payload()

    log_output = StringIO()
    handler_id = logger.add(
        log_output,
        format="{extra} {message}",
        level="DEBUG",
        filter=lambda r: "request_id" in r["extra"],
    )
    try:
        with patch("backend.app.api.webhooks._handle_welcome_state", new_callable=AsyncMock):
            await _dispatch(payload, "req-new-789", redis)
        log_text = log_output.getvalue().lower()
        assert "new" in log_text or "no session" in log_text
    finally:
        logger.remove(handler_id)
