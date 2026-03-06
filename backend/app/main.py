"""S1.4 — FastAPI App Factory.

Provides create_app() factory and module-level `app` for uvicorn.
Lifespan manages startup/shutdown hooks for DB (S2.1) and Redis (S2.2).
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from backend.app.api.dashboard import router as dashboard_router
from backend.app.api.web import router as web_router
from backend.app.api.webhooks import router as webhooks_router
from backend.app.db.database import close_db, init_db
from backend.app.db.redis import close_redis, init_redis

# Resolve paths relative to this file
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_STATIC_DIR = _BACKEND_DIR / "static"
_TEMPLATES_DIR = _BACKEND_DIR / "templates"


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

    # CORS — allow all origins for prototype
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(webhooks_router, prefix="/webhook", tags=["webhook"])
    app.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
    app.include_router(web_router, prefix="/api", tags=["web"])

    # Static files
    if _STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # Templates
    templates = None
    if _TEMPLATES_DIR.exists():
        templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def landing_page(request: Request):
        if templates:
            from backend.app.services.whatsapp import SUPPORTED_LANGUAGES

            return templates.TemplateResponse(
                "index.html",
                {"request": request, "languages": SUPPORTED_LANGUAGES},
            )
        return HTMLResponse("<h1>SehatSamjho</h1><p>Templates not found.</p>")

    return app


app = create_app()
