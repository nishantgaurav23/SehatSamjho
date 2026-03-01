"""Tests for S1.4 — FastAPI App Factory.

Red → Green → Refactor.
10 tests covering create_app(), lifespan, /health, routers, module-level app.
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
}
for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.routing import APIRouter  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from loguru import logger  # noqa: E402


# ---------- Test 1: create_app returns FastAPI instance ----------
def test_create_app_returns_fastapi_instance():
    from backend.app.main import create_app

    app = create_app()
    assert isinstance(app, FastAPI)


# ---------- Test 2: app title and version ----------
def test_app_title_and_version():
    from backend.app.main import create_app

    app = create_app()
    assert app.title == "SehatSamjho"
    assert app.version == "0.1.0"


# ---------- Test 3: GET /health returns 200 {"status": "ok"} ----------
@pytest.mark.asyncio
async def test_health_endpoint_returns_ok():
    from backend.app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------- Test 4: webhook router included ----------
def test_webhook_router_included():
    """Verify /webhook prefix is registered by adding a temp route to the stub router."""
    from backend.app.api.webhooks import router as webhooks_router

    # Add a temporary probe route to the empty stub router
    @webhooks_router.get("/probe")
    async def _probe():
        return {}

    from backend.app.main import create_app

    app = create_app()
    route_paths = [getattr(r, "path", "") for r in app.routes]
    assert any(p.startswith("/webhook") for p in route_paths)

    # Clean up: remove the probe route
    webhooks_router.routes = [
        r for r in webhooks_router.routes if getattr(r, "path", "") != "/probe"
    ]


# ---------- Test 5: dashboard router included ----------
def test_dashboard_router_included():
    """Verify /dashboard prefix is registered by adding a temp route to the stub router."""
    from backend.app.api.dashboard import router as dashboard_router

    @dashboard_router.get("/probe")
    async def _probe():
        return {}

    from backend.app.main import create_app

    app = create_app()
    route_paths = [getattr(r, "path", "") for r in app.routes]
    assert any(p.startswith("/dashboard") for p in route_paths)

    dashboard_router.routes = [
        r for r in dashboard_router.routes if getattr(r, "path", "") != "/probe"
    ]


# ---------- Test 6: lifespan logs startup and shutdown ----------
@pytest.mark.asyncio
async def test_lifespan_logs_startup_and_shutdown():
    from unittest.mock import AsyncMock, patch

    from backend.app.main import create_app, lifespan

    app = create_app()
    captured: list[str] = []

    def sink(message):
        captured.append(str(message))

    handler_id = logger.add(sink, format="{message}")
    try:
        with (
            patch("backend.app.main.init_db", new_callable=AsyncMock),
            patch("backend.app.main.close_db", new_callable=AsyncMock),
            patch("backend.app.main.init_redis", new_callable=AsyncMock),
            patch("backend.app.main.close_redis", new_callable=AsyncMock),
        ):
            async with lifespan(app):
                pass  # startup has fired, shutdown fires on exit
    finally:
        logger.remove(handler_id)

    combined = "\n".join(captured)
    assert "SehatSamjho starting up" in combined
    assert "SehatSamjho shutting down" in combined


# ---------- Test 7: create_app returns independent instances ----------
def test_create_app_independent_instances():
    from backend.app.main import create_app

    app1 = create_app()
    app2 = create_app()
    assert app1 is not app2


# ---------- Test 8: module-level app exists ----------
def test_module_level_app_exists():
    from backend.app.main import app

    assert isinstance(app, FastAPI)


# ---------- Test 9: webhooks router importable ----------
def test_webhooks_router_importable():
    from backend.app.api.webhooks import router

    assert isinstance(router, APIRouter)


# ---------- Test 10: dashboard router importable ----------
def test_dashboard_router_importable():
    from backend.app.api.dashboard import router

    assert isinstance(router, APIRouter)
