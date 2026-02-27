"""
SehatSamjho FastAPI application entry point.

Registers:
    POST /webhook/whatsapp — Twilio WhatsApp webhook  (api/webhooks.py)
    GET  /dashboard/*      — B2B analytics endpoints  (api/dashboard.py)
    GET  /health           — Docker / ECS health check

Lifespan:
    startup  — verify PostgreSQL connectivity, log config summary
    shutdown — dispose DB engine connection pool

Run locally (no Docker):
    source .venv/bin/activate
    cd backend
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    logger.info(
        f"SehatSamjho starting — env={settings.environment} "
        f"debug={settings.debug} audio={settings.enable_audio}"
    )

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connection verified")
    except Exception as exc:
        # Log but don't crash — health check will surface the failure
        logger.error(f"PostgreSQL connection failed at startup: {exc}")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────────
    logger.info("SehatSamjho shutting down — disposing DB engine")
    await engine.dispose()


app = FastAPI(
    title="SehatSamjho API",
    description="AI Medical Document Translator via WhatsApp",
    version="0.1.0",
    lifespan=lifespan,
    # Hide interactive docs in production
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)


# ── Routes ─────────────────────────────────────────────────────────────────────
# Imported here (not at module top) to avoid circular imports when service
# modules import from app.core.config at load time.

from app.api import dashboard, webhooks  # noqa: E402

app.include_router(webhooks.router, tags=["webhook"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])


@app.get("/health", tags=["infra"])
async def health():
    """Liveness probe for Docker / AWS ECS.

    Returns 200 if the API process is alive.
    DB connectivity is verified separately at startup.
    """
    return {"status": "ok", "env": settings.environment}
