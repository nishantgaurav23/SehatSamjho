# Spec S1.4 — FastAPI App Factory

## Overview
Create the FastAPI application entry point with an async lifespan that connects to
PostgreSQL and Redis on startup and disconnects on shutdown.  Include router stubs
for webhooks and the B2B dashboard, plus a `GET /health` endpoint returning
`{"status": "ok"}`.  After this spec, `make local-dev` starts a healthy server.

## Dependencies
- **S1.3** — pydantic-settings config (`backend/app/core/config.py` must exist and
  export `settings`)

## Target Location
- `backend/app/main.py`

---

## Functional Requirements

### FR-1: `create_app()` factory function
- **What**: A function that builds and returns a fully configured `FastAPI` instance.
  Using a factory (instead of a bare module-level `app = FastAPI()`) makes testing
  easier — each test can get a fresh app.
- **Inputs**: None.
- **Outputs**: `FastAPI` instance with title `"SehatSamjho"`, version `"0.1.0"`,
  lifespan attached, routers included.
- **Edge cases**: Called multiple times — each invocation returns an independent app.

### FR-2: Async lifespan (startup / shutdown)
- **What**: An `@asynccontextmanager` lifespan that:
  - **Startup**: Logs `"SehatSamjho starting up"` via Loguru. (Actual DB/Redis
    connection will be wired in S2.1 / S2.2 — for now the lifespan is a placeholder
    that yields.)
  - **Shutdown**: Logs `"SehatSamjho shutting down"`.
- **Inputs**: The `FastAPI` app instance (standard lifespan signature).
- **Outputs**: Side effects only (logging).
- **Edge cases**: If startup raises, the app must not start (FastAPI default behaviour).

### FR-3: Router inclusion
- **What**: `create_app()` includes two routers:
  1. `webhooks_router` — prefix `/webhook`, tags `["webhook"]`.
  2. `dashboard_router` — prefix `/dashboard`, tags `["dashboard"]`.
- **Inputs**: Router objects imported from `backend/app/api/webhooks.py` and
  `backend/app/api/dashboard.py`.
- **Outputs**: Routes registered on the app.
- **Edge cases**: Routers may be empty stubs (no routes yet).  Importing them must
  not fail.

### FR-4: Stub router files
- **What**: Create two minimal router modules:
  - `backend/app/api/__init__.py` (empty)
  - `backend/app/api/webhooks.py` — defines `router = APIRouter()` (no routes yet).
  - `backend/app/api/dashboard.py` — defines `router = APIRouter()` (no routes yet).
- **Inputs**: N/A.
- **Outputs**: Importable `router` from each module.

### FR-5: `GET /health` endpoint
- **What**: A health-check endpoint on the root app (not behind a router prefix).
  Returns `{"status": "ok"}` with HTTP 200.
- **Inputs**: None.
- **Outputs**: `{"status": "ok"}` (JSON).
- **Edge cases**: Must be reachable even if DB/Redis are down (no dependency
  injection for this endpoint).

### FR-6: Module-level `app` for uvicorn
- **What**: `backend/app/main.py` exposes `app = create_app()` at module level so
  that `uvicorn backend.app.main:app` works.
- **Inputs**: N/A.
- **Outputs**: A module attribute `app` of type `FastAPI`.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `from backend.app.main import app` succeeds and `app` is a
  `FastAPI` instance.
- [ ] **Outcome 2**: `GET /health` returns `{"status": "ok"}` with status 200.
- [ ] **Outcome 3**: `GET /docs` returns the Swagger UI (default FastAPI behaviour,
  verifies app is configured).
- [ ] **Outcome 4**: `/webhook` and `/dashboard` prefixes are registered (visible in
  `app.routes` or OpenAPI schema).
- [ ] **Outcome 5**: Lifespan logs startup and shutdown messages.
- [ ] **Outcome 6**: `create_app()` can be called multiple times returning
  independent apps.

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
Test file: `backend/tests/test_s1_4_fastapi_app_factory.py`

1. **test_create_app_returns_fastapi_instance**: `create_app()` returns a `FastAPI`
   object.
2. **test_app_title_and_version**: `app.title == "SehatSamjho"` and
   `app.version == "0.1.0"`.
3. **test_health_endpoint_returns_ok**: `GET /health` returns 200 with
   `{"status": "ok"}`.
4. **test_webhook_router_included**: A route path starting with `/webhook` exists in
   `app.routes`.
5. **test_dashboard_router_included**: A route path starting with `/dashboard` exists
   in `app.routes`.
6. **test_lifespan_logs_startup_and_shutdown**: Using `httpx.AsyncClient` as a
   lifespan context, verify Loguru emitted the startup and shutdown messages
   (capture logs with a Loguru sink).
7. **test_create_app_independent_instances**: Two calls to `create_app()` return
   different objects (`app1 is not app2`).
8. **test_module_level_app_exists**: `from backend.app.main import app` succeeds and
   `isinstance(app, FastAPI)`.
9. **test_webhooks_router_importable**: `from backend.app.api.webhooks import router`
   succeeds and `isinstance(router, APIRouter)`.
10. **test_dashboard_router_importable**: `from backend.app.api.dashboard import router`
    succeeds and `isinstance(router, APIRouter)`.

### Mocking Strategy
- **No external services to mock** for this spec.  Config is loaded at import time
  but tests already have env vars set via conftest.py (from S1.3).
- Lifespan is a placeholder — no DB/Redis connections to mock.

### Coverage Expectation
- All 10 tests green.  100% coverage of `main.py`, `api/webhooks.py`,
  `api/dashboard.py`.

---

## References
- roadmap.md — Phase 1, S1.4
- CLAUDE.md — Project Structure, Core Flow
- FastAPI lifespan docs: https://fastapi.tiangolo.com/advanced/events/#lifespan
