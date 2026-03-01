# Spec S1.2 — Developer Commands

## Overview
A root-level `Makefile` providing all developer commands needed for local development, testing, linting, and Docker-based workflows. Targets cover virtual environment creation, dependency installation, running the FastAPI dev server, executing tests and linting, database migrations, data seeding, and Docker Compose orchestration. Every common developer action is a single `make <target>` away.

## Dependencies
None (S1.2 has no spec prerequisites).

## Target Location
`Makefile` (project root)

---

## Functional Requirements

### FR-1: Virtual environment creation (`make venv`)
- **What**: Creates a Python virtual environment at `.venv` in the project root using Python 3.11
- **Inputs**: None (uses system Python 3.11)
- **Outputs**: `.venv/` directory created with a working Python interpreter
- **Edge cases**: `.venv` already exists (should be a no-op or recreate); Python 3.11 not found (fail with clear error)

### FR-2: Dependency installation (`make install`)
- **What**: Installs runtime dependencies from `pyproject.toml` into the active venv using `uv`
- **Inputs**: Active `.venv`, `pyproject.toml` at root
- **Outputs**: All 14 runtime dependencies installed
- **Edge cases**: `uv` not installed (fail with clear error); `.venv` not activated (should activate or instruct)

### FR-3: Dev dependency installation (`make install-dev`)
- **What**: Installs runtime + dev extra dependencies from `pyproject.toml` using `uv`
- **Inputs**: Active `.venv`, `pyproject.toml` at root
- **Outputs**: All runtime + 5 dev extras installed (pytest, pytest-asyncio, httpx, ruff, pytest-mock)
- **Edge cases**: Same as FR-2

### FR-4: Local dev server (`make local-dev`)
- **What**: Starts the FastAPI server via uvicorn with hot reload on port 8000
- **Inputs**: Active `.venv` with dependencies installed
- **Outputs**: Server running at `http://0.0.0.0:8000` with `--reload` flag
- **Edge cases**: Port 8000 in use; missing `.env` file (should fail with config error, not silently)

### FR-5: Local test runner (`make local-test`)
- **What**: Runs pytest from the `backend/` directory with verbose output
- **Inputs**: Active `.venv` with dev dependencies installed
- **Outputs**: pytest output with `-v --tb=short` flags
- **Edge cases**: No tests found (should still exit cleanly); test failures (non-zero exit code propagated)

### FR-6: Local linter (`make local-lint`)
- **What**: Runs ruff check + ruff format (check mode) on the `backend/` directory
- **Inputs**: Active `.venv` with ruff installed
- **Outputs**: Linting results; non-zero exit on violations
- **Edge cases**: No Python files; ruff not installed

### FR-7: Local migration (`make local-migrate`)
- **What**: Runs `alembic upgrade head` from the `backend/` directory
- **Inputs**: Active `.venv`, valid `DATABASE_URL` in `.env`, alembic config present
- **Outputs**: Database schema updated to latest migration
- **Edge cases**: No migrations to run (no-op); database unreachable (fail with error)

### FR-8: Docker dev stack (`make dev`)
- **What**: Runs `docker-compose up --build` to start the full local dev stack (app + postgres + redis)
- **Inputs**: Docker + docker-compose installed, `docker-compose.yml` present
- **Outputs**: All containers running, app accessible on port 8000
- **Edge cases**: Docker not running; port conflicts

### FR-9: Docker test runner (`make test`)
- **What**: Runs pytest inside the Docker app container
- **Inputs**: Docker dev stack running or buildable
- **Outputs**: pytest results from container
- **Edge cases**: Container not built; dependency issues

### FR-10: Docker migration (`make migrate`)
- **What**: Runs alembic migration inside the Docker app container
- **Inputs**: Docker dev stack running, database accessible
- **Outputs**: Database schema updated
- **Edge cases**: Container not running

### FR-11: Data seeding (`make seed`)
- **What**: Loads drug CSV + glossary JSON data into Redis
- **Inputs**: Docker or local environment with Redis running, data files present
- **Outputs**: Redis populated with drug + glossary data
- **Edge cases**: Redis not reachable; data files missing

---

## Tangible Outcomes

- [ ] **Outcome 1**: `Makefile` exists at project root with all 11 targets defined
- [ ] **Outcome 2**: `make venv` creates a `.venv/` directory with Python 3.11
- [ ] **Outcome 3**: `make install` installs runtime deps (e.g., `python -c "import fastapi"` succeeds)
- [ ] **Outcome 4**: `make install-dev` installs dev deps (e.g., `python -c "import pytest"` succeeds)
- [ ] **Outcome 5**: `make local-dev` launches uvicorn on port 8000 with reload
- [ ] **Outcome 6**: `make local-test` runs pytest with `-v --tb=short` from `backend/`
- [ ] **Outcome 7**: `make local-lint` runs `ruff check` + `ruff format --check` on `backend/`
- [ ] **Outcome 8**: `make local-migrate` runs `alembic upgrade head` from `backend/`
- [ ] **Outcome 9**: `make dev` runs `docker-compose up --build`
- [ ] **Outcome 10**: `make test` runs pytest inside Docker container
- [ ] **Outcome 11**: `make migrate` runs alembic inside Docker container
- [ ] **Outcome 12**: `make seed` runs seed script to load data into Redis
- [ ] **Outcome 13**: All targets use `.PHONY` declarations (no file-based make caching)
- [ ] **Outcome 14**: Makefile uses tabs (not spaces) for recipe indentation

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_makefile_exists**: Verify `Makefile` exists at project root
2. **test_makefile_has_all_targets**: Parse Makefile and verify all 11 targets are defined: `venv`, `install`, `install-dev`, `local-dev`, `local-test`, `local-lint`, `local-migrate`, `seed`, `dev`, `test`, `migrate`
3. **test_makefile_phony_declarations**: Verify all targets are declared as `.PHONY`
4. **test_makefile_venv_target_uses_python311**: Verify `venv` target references Python 3.11
5. **test_makefile_install_uses_uv**: Verify `install` target uses `uv pip install`
6. **test_makefile_install_dev_uses_uv**: Verify `install-dev` target uses `uv pip install` with dev extras
7. **test_makefile_local_dev_uses_uvicorn**: Verify `local-dev` target runs uvicorn with `--reload`
8. **test_makefile_local_test_uses_pytest**: Verify `local-test` target runs `python -m pytest` with `-v --tb=short`
9. **test_makefile_local_lint_uses_ruff**: Verify `local-lint` target runs `ruff check` and `ruff format`
10. **test_makefile_local_migrate_uses_alembic**: Verify `local-migrate` target runs `alembic upgrade head`
11. **test_makefile_dev_target_uses_docker_compose**: Verify `dev` target runs `docker-compose up --build` or `docker compose up --build`
12. **test_makefile_test_target_uses_docker**: Verify `test` target runs pytest inside Docker
13. **test_makefile_migrate_target_uses_docker**: Verify `migrate` target runs alembic inside Docker
14. **test_makefile_seed_target_defined**: Verify `seed` target runs the seed script
15. **test_makefile_uses_tabs**: Verify recipe lines use tabs (not spaces) for indentation

### Mocking Strategy
- No external services needed — tests are purely static file validation (parsing the Makefile text)

### Coverage Expectation
- All 11 targets verified for existence and correct command patterns
- Tab indentation and `.PHONY` declarations validated
- 100% of functional requirements covered by at least one test

---

## References
- roadmap.md (Phase 1, S1.2 row)
- CLAUDE.md (Commands section)
