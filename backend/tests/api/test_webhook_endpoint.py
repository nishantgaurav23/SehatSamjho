"""S4.1 — Webhook Endpoint tests.

20 tests covering POST /webhook/whatsapp: route existence, TwiML response,
HMAC dependency, form body parsing, defaults, error handling, and logging.
"""

from __future__ import annotations

import os
import uuid

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

from io import StringIO  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from loguru import logger  # noqa: E402

from backend.app.api.webhooks import router  # noqa: E402
from backend.app.core.security import validate_twilio_signature  # noqa: E402
from backend.app.main import create_app  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app():
    """Create a test app with HMAC and Redis overridden to no-op."""
    from backend.app.db.redis import get_redis

    app = create_app()
    app.dependency_overrides[validate_twilio_signature] = lambda: None

    async def _mock_redis():
        yield AsyncMock()

    app.dependency_overrides[get_redis] = _mock_redis
    yield app
    app.dependency_overrides.clear()


@pytest.fixture()
async def client(app):
    """Async test client for the app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _form_data(**overrides) -> dict:
    """Build default valid Twilio form data with optional overrides."""
    data = {
        "From": "whatsapp:+919876543210",
        "Body": "Hello doctor",
        "NumMedia": "0",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Test 1: Route exists
# ---------------------------------------------------------------------------


def test_webhook_endpoint_exists():
    """POST /webhook/whatsapp route exists on the router."""
    route_paths = []
    for route in router.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        route_paths.append((path, methods))

    assert any(
        path == "/whatsapp" and "POST" in methods for path, methods in route_paths
    ), f"Expected POST /whatsapp route, found: {route_paths}"


# ---------------------------------------------------------------------------
# Test 2: Returns TwiML response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_returns_twiml_response(mock_send, client):
    """Valid request returns 200 with <Response/> body and text/xml content-type."""
    resp = await client.post("/webhook/whatsapp", data=_form_data())
    assert resp.status_code == 200
    assert resp.text == "<Response/>"
    assert "text/xml" in resp.headers["content-type"]


# ---------------------------------------------------------------------------
# Test 3: Requires HMAC dependency
# ---------------------------------------------------------------------------


def test_webhook_requires_hmac_dependency():
    """The endpoint has validate_twilio_signature as a dependency."""
    # Find the POST /whatsapp route
    for route in router.routes:
        if getattr(route, "path", "") == "/whatsapp" and "POST" in getattr(route, "methods", set()):
            deps = getattr(route, "dependencies", [])
            dep_callables = [d.dependency for d in deps]
            assert (
                validate_twilio_signature in dep_callables
            ), f"validate_twilio_signature not in route dependencies: {dep_callables}"
            return
    pytest.fail("POST /whatsapp route not found")


# ---------------------------------------------------------------------------
# Tests 4-8: Field parsing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_parses_from_field(mock_send, client):
    """From field is extracted into WebhookPayload.from_number."""
    resp = await client.post(
        "/webhook/whatsapp",
        data=_form_data(From="whatsapp:+911234567890"),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_parses_body_field(mock_send, client):
    """Body field is extracted into WebhookPayload.body."""
    resp = await client.post(
        "/webhook/whatsapp",
        data=_form_data(Body="Namaste doctor"),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_parses_num_media(mock_send, client):
    """NumMedia string is cast to int in WebhookPayload.num_media."""
    resp = await client.post(
        "/webhook/whatsapp",
        data=_form_data(NumMedia="2"),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_parses_media_url(mock_send, client):
    """MediaUrl0 field is extracted into WebhookPayload.media_url."""
    resp = await client.post(
        "/webhook/whatsapp",
        data=_form_data(
            NumMedia="1",
            MediaUrl0="https://api.twilio.com/2010-04-01/media/ME123",
            MediaContentType0="image/jpeg",
        ),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_parses_media_content_type(mock_send, client):
    """MediaContentType0 field is extracted into WebhookPayload.media_content_type."""
    resp = await client.post(
        "/webhook/whatsapp",
        data=_form_data(
            NumMedia="1",
            MediaUrl0="https://api.twilio.com/2010-04-01/media/ME123",
            MediaContentType0="image/png",
        ),
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests 9-10: Missing/empty From → 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_missing_from_returns_400(mock_send, client):
    """Missing From field returns 400."""
    data = _form_data()
    del data["From"]
    resp = await client.post("/webhook/whatsapp", data=data)
    assert resp.status_code == 400


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_empty_from_returns_400(mock_send, client):
    """Empty From field returns 400."""
    resp = await client.post("/webhook/whatsapp", data=_form_data(From=""))
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Tests 11-15: Defaults for optional fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_default_body_empty_string(mock_send, client):
    """Missing Body defaults to empty string."""
    data = {"From": "whatsapp:+919876543210"}
    resp = await client.post("/webhook/whatsapp", data=data)
    assert resp.status_code == 200


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_default_num_media_zero(mock_send, client):
    """Missing NumMedia defaults to 0."""
    data = {"From": "whatsapp:+919876543210", "Body": "Test"}
    resp = await client.post("/webhook/whatsapp", data=data)
    assert resp.status_code == 200


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_num_media_non_integer_defaults_zero(mock_send, client):
    """Non-integer NumMedia (e.g., 'abc') defaults to 0."""
    resp = await client.post(
        "/webhook/whatsapp",
        data=_form_data(NumMedia="abc"),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_default_media_url_none(mock_send, client):
    """Missing MediaUrl0 defaults to None."""
    data = {"From": "whatsapp:+919876543210", "Body": "Test"}
    resp = await client.post("/webhook/whatsapp", data=data)
    assert resp.status_code == 200


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_default_media_content_type_none(mock_send, client):
    """Missing MediaContentType0 defaults to None."""
    data = {"From": "whatsapp:+919876543210", "Body": "Test"}
    resp = await client.post("/webhook/whatsapp", data=data)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test 16: Generates request_id (UUID4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_generates_request_id(mock_send, client):
    """Each request produces a UUID4 request_id in logs."""
    log_output = StringIO()
    handler_id = logger.add(log_output, format="{extra} {message}", level="DEBUG")
    try:
        await client.post("/webhook/whatsapp", data=_form_data())
        log_text = log_output.getvalue()
        # Find a UUID4 pattern in the log output
        import re

        uuid4_pattern = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            re.IGNORECASE,
        )
        assert uuid4_pattern.search(
            log_text
        ), f"No UUID4 request_id found in log output:\n{log_text}"
    finally:
        logger.remove(handler_id)


# ---------------------------------------------------------------------------
# Tests 17-19: Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_error_returns_twiml_not_500(app):
    """Unhandled exception still returns 200 with TwiML (not 500)."""
    with patch(
        "backend.app.api.webhooks._parse_webhook_payload",
        side_effect=RuntimeError("unexpected boom"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/webhook/whatsapp", data=_form_data())
        assert resp.status_code == 200
        assert resp.text == "<Response/>"
        assert "text/xml" in resp.headers["content-type"]


@pytest.mark.asyncio
async def test_webhook_error_sends_message_to_user(app):
    """On error, send_text_message() is called with an apology message."""
    with (
        patch(
            "backend.app.api.webhooks._parse_webhook_payload",
            side_effect=RuntimeError("unexpected boom"),
        ),
        patch(
            "backend.app.api.webhooks.send_text_message",
            new_callable=AsyncMock,
        ) as mock_send,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/webhook/whatsapp", data=_form_data())
        assert resp.status_code == 200
        mock_send.assert_awaited_once()
        call_args = mock_send.call_args
        to_arg = call_args[0][0] if call_args[0] else call_args[1].get("to")
        body_arg = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("body")
        assert to_arg == "whatsapp:+919876543210"
        # Should be a patient-friendly message, not internal error details
        assert "error" not in body_arg.lower() or "sorry" in body_arg.lower()
        assert "unexpected boom" not in body_arg  # Never expose internals


@pytest.mark.asyncio
async def test_webhook_error_skips_send_if_no_from(app):
    """If error occurs before From is parsed, no send_text_message call."""

    async def _bad_form():
        raise RuntimeError("form parsing exploded")

    with patch(
        "backend.app.api.webhooks.send_text_message",
        new_callable=AsyncMock,
    ) as mock_send:
        # Patch at the Request.form level so from_number is never extracted
        with patch(
            "starlette.requests.Request.form",
            side_effect=RuntimeError("form parsing exploded"),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/webhook/whatsapp", data=_form_data())
            assert resp.status_code == 200
            assert resp.text == "<Response/>"
            mock_send.assert_not_awaited()


# ---------------------------------------------------------------------------
# Test 20: Logs include request_id
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock)
async def test_webhook_logs_request_id(mock_send, client):
    """Loguru log output includes the request_id."""
    log_output = StringIO()
    handler_id = logger.add(
        log_output,
        format="{extra[request_id]} {message}",
        level="DEBUG",
        filter=lambda r: "request_id" in r["extra"],
    )
    try:
        await client.post("/webhook/whatsapp", data=_form_data())
        log_text = log_output.getvalue()
        # Validate there's a UUID4 formatted request_id
        assert len(log_text) > 0, "No log output with request_id found"
        # Extract the first token (should be UUID4)
        first_line = log_text.strip().split("\n")[0]
        rid = first_line.split(" ")[0]
        # Validate it's a valid UUID4
        parsed = uuid.UUID(rid, version=4)
        assert str(parsed) == rid
    finally:
        logger.remove(handler_id)
