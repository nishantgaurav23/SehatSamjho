"""Tests for app/main.py

Tests:
    - GET /health returns 200 with correct payload
    - /docs is accessible in debug mode
    - App title and version are correct

Requires PostgreSQL running — start with `make services`.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def base_url():
    return "http://testserver"


# ── Health check ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_returns_200(base_url):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_payload(base_url):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        response = await client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "env" in data


@pytest.mark.asyncio
async def test_health_env_matches_settings(base_url):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        response = await client.get("/health")
    assert response.json()["env"] == settings.environment


@pytest.mark.asyncio
async def test_docs_accessible_in_debug_mode(base_url):
    """Swagger UI is served when debug=True."""
    if not settings.debug:
        pytest.skip("docs only available in debug mode")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=base_url) as client:
        response = await client.get("/docs")
    assert response.status_code == 200


# ── App metadata ───────────────────────────────────────────────────────────────

def test_app_title():
    assert app.title == "SehatSamjho API"


def test_app_version():
    assert app.version == "0.1.0"
