# Checklist — Spec S1.4: FastAPI App Factory

## Phase 1: Setup & Dependencies
- [x] Verify S1.3 (pydantic-settings) is implemented and tests pass
- [x] Create target files: `backend/app/main.py`, `backend/app/api/__init__.py`,
      `backend/app/api/webhooks.py`, `backend/app/api/dashboard.py`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s1_4_fastapi_app_factory.py`
- [x] test_create_app_returns_fastapi_instance
- [x] test_app_title_and_version
- [x] test_health_endpoint_returns_ok
- [x] test_webhook_router_included
- [x] test_dashboard_router_included
- [x] test_lifespan_logs_startup_and_shutdown
- [x] test_create_app_independent_instances
- [x] test_module_level_app_exists
- [x] test_webhooks_router_importable
- [x] test_dashboard_router_importable
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Create `backend/app/api/__init__.py` (empty)
- [x] Create `backend/app/api/webhooks.py` — stub `router = APIRouter()`
- [x] Create `backend/app/api/dashboard.py` — stub `router = APIRouter()`
- [x] Implement `backend/app/main.py`:
  - [x] `lifespan()` async context manager with startup/shutdown Loguru logs
  - [x] `create_app()` factory: title, version, lifespan, include routers, /health
  - [x] Module-level `app = create_app()`
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `make local-dev` starts uvicorn and /health returns 200
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 10 tests passing
- [x] All 6 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging uses Loguru (not stdlib logging)
- [x] Update roadmap.md status: spec-written -> done
