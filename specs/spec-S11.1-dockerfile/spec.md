# Spec S11.1 — Multi-stage Dockerfile

## Overview
Create a multi-stage Dockerfile for the SehatSamjho backend. Stage 1 (base) installs Python 3.11-slim and uses `uv` to install production dependencies from `pyproject.toml`. Stage 2 (dev) extends base with test/lint tools (pytest, ruff). Stage 3 (prod) copies the application code, creates a non-root user, and sets `uvicorn` as the CMD. The build context is the repo root (not `./backend`).

## Dependencies
- S1.1 (Dependency declaration — `pyproject.toml` must exist with all runtime + dev deps)

## Target Location
- `backend/Dockerfile`

---

## Functional Requirements

### FR-1: Base stage (`base`)
- **What**: First Docker stage named `base` using `python:3.11-slim` as the parent image.
- **Inputs**: `pyproject.toml` from repo root.
- **Outputs**: A Docker layer with Python 3.11, `uv` installed, and all production dependencies from `pyproject.toml` installed into the system Python (no venv inside Docker).
- **Details**:
  - Install `uv` via `pip install uv` or `curl` installer.
  - Set `WORKDIR /app`.
  - Copy `pyproject.toml` first (layer caching — deps only rebuild when pyproject.toml changes).
  - Run `uv pip install --system -r pyproject.toml` to install runtime deps.
  - Set `PYTHONUNBUFFERED=1` and `PYTHONDONTWRITEBYTECODE=1` env vars.

### FR-2: Dev stage (`dev`)
- **What**: Second Docker stage named `dev` extending `base`.
- **Inputs**: None beyond base stage.
- **Outputs**: A Docker image with all runtime deps PLUS dev extras (pytest, ruff, pytest-asyncio, pytest-mock, httpx).
- **Details**:
  - `FROM base AS dev`
  - Install dev extras: `uv pip install --system -r pyproject.toml --extra dev` (or equivalent).
  - Copy entire backend source code: `COPY backend/ /app/backend/`
  - Copy data files: `COPY data/ /app/data/`
  - CMD can be `pytest` or `bash` for interactive use.

### FR-3: Prod stage (`prod`)
- **What**: Third Docker stage named `prod` extending `base`.
- **Inputs**: Application source from repo.
- **Outputs**: A production-ready Docker image with non-root user and uvicorn entrypoint.
- **Details**:
  - `FROM base AS prod`
  - Copy backend source: `COPY backend/ /app/backend/`
  - Copy data files: `COPY data/ /app/data/`
  - Copy alembic config: `COPY backend/alembic.ini /app/backend/alembic.ini` (if not already included)
  - Create non-root user: `RUN useradd --create-home appuser && chown -R appuser /app`
  - `USER appuser`
  - `EXPOSE 8000`
  - `CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]`

### FR-4: Build context expectations
- **What**: Dockerfile expects build context = repo root.
- **Details**:
  - `docker build -f backend/Dockerfile .` (from repo root)
  - All COPY paths are relative to repo root (e.g., `COPY pyproject.toml /app/pyproject.toml`, `COPY backend/ /app/backend/`)
  - Dockerfile lives at `backend/Dockerfile` but is NOT the build context.

### FR-5: Layer caching optimization
- **What**: Dockerfile is structured for optimal layer caching.
- **Details**:
  - Copy `pyproject.toml` before source code so dependency layer is cached.
  - Source code changes do NOT trigger dependency reinstall.
  - `.dockerignore` (S11.4) will further optimize build context size.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `backend/Dockerfile` exists and is valid Dockerfile syntax.
- [ ] **Outcome 2**: Dockerfile has exactly 3 named stages: `base`, `dev`, `prod`.
- [ ] **Outcome 3**: Base stage uses `python:3.11-slim` and installs `uv`.
- [ ] **Outcome 4**: Base stage copies `pyproject.toml` and installs deps with `uv pip install --system`.
- [ ] **Outcome 5**: Base stage sets `PYTHONUNBUFFERED=1` and `PYTHONDONTWRITEBYTECODE=1`.
- [ ] **Outcome 6**: Dev stage extends base and installs dev extras (pytest, ruff).
- [ ] **Outcome 7**: Prod stage extends base, copies source, creates non-root `appuser`, runs as `appuser`.
- [ ] **Outcome 8**: Prod stage exposes port 8000 and has uvicorn CMD.
- [ ] **Outcome 9**: Prod CMD references `backend.app.main:app`.
- [ ] **Outcome 10**: All COPY paths assume build context is repo root.

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_dockerfile_exists**: `backend/Dockerfile` file exists.
2. **test_dockerfile_valid_syntax**: File starts with `FROM` and contains no obvious syntax errors.
3. **test_three_named_stages**: Dockerfile has exactly 3 `FROM ... AS ...` lines: `base`, `dev`, `prod`.
4. **test_base_stage_python_311_slim**: Base stage uses `python:3.11-slim`.
5. **test_base_installs_uv**: Base stage has a `pip install uv` or equivalent uv installation.
6. **test_base_copies_pyproject_before_source**: `COPY pyproject.toml` appears before `COPY backend/`.
7. **test_base_uv_pip_install**: Base stage runs `uv pip install --system`.
8. **test_base_pythonunbuffered**: `PYTHONUNBUFFERED=1` is set via ENV.
9. **test_base_pythondontwritebytecode**: `PYTHONDONTWRITEBYTECODE=1` is set via ENV.
10. **test_base_workdir**: `WORKDIR /app` is set in base stage.
11. **test_dev_extends_base**: Dev stage `FROM base AS dev`.
12. **test_dev_installs_dev_extras**: Dev stage installs dev extras (pytest, ruff present).
13. **test_dev_copies_backend**: Dev stage copies backend source.
14. **test_dev_copies_data**: Dev stage copies data directory.
15. **test_prod_extends_base**: Prod stage `FROM base AS prod`.
16. **test_prod_copies_backend**: Prod stage copies backend source.
17. **test_prod_copies_data**: Prod stage copies data directory.
18. **test_prod_creates_nonroot_user**: Prod stage creates `appuser` and switches to it.
19. **test_prod_exposes_8000**: Prod stage has `EXPOSE 8000`.
20. **test_prod_cmd_uvicorn**: Prod CMD runs uvicorn with `backend.app.main:app`.

### Mocking Strategy
- No mocking needed — these are static file validation tests (similar to S1.1, S1.2, S2.5).
- Tests parse the Dockerfile text directly.

### Coverage Expectation
- All stages, directives, and key behaviors validated via static file parsing.

---

## References
- roadmap.md (Phase 11, S11.1)
- pyproject.toml (dependency source of truth)
- S1.1 spec (dependency declaration)
- Docker multi-stage build docs
