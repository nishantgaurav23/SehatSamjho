"""S1.4 — FastAPI App Factory.

Provides create_app() factory and module-level `app` for uvicorn.
Lifespan manages startup/shutdown hooks for DB (S2.1) and Redis (S2.2).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from backend.app.api.dashboard import router as dashboard_router
from backend.app.api.webhooks import router as webhooks_router
from backend.app.db.database import close_db, init_db
from backend.app.db.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Async lifespan: startup and shutdown hooks."""
    logger.info("SehatSamjho starting up")
    await init_db()
    await init_redis()
    yield
    await close_redis()
    await close_db()
    logger.info("SehatSamjho shutting down")


def create_app() -> FastAPI:
    """Build and return a fully configured FastAPI instance."""
    app = FastAPI(
        title="SehatSamjho",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(webhooks_router, prefix="/webhook", tags=["webhook"])
    app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
