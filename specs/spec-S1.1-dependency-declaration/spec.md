# Spec S1.1 — Dependency Declaration

## Overview
Declare all project dependencies in a single `pyproject.toml` at the repository root and provide a `.env.example` template listing every required environment variable. This is the foundation spec — no external services are connected yet. The goal is that `uv pip install -r pyproject.toml` installs everything needed for runtime and (with dev extras) for testing/linting.

## Dependencies
None — this is the first spec.

## Target Location
- `pyproject.toml` (repo root)
- `.env.example` (repo root)

---

## Functional Requirements

### FR-1: pyproject.toml with all runtime dependencies
- **What**: A valid `pyproject.toml` at the repo root declaring the project metadata and all runtime dependencies.
- **Inputs**: N/A (static file)
- **Outputs**: A PEP 621-compliant `pyproject.toml` that `uv` can install from.
- **Required runtime deps**: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `aioredis`, `anthropic`, `openai`, `tenacity`, `loguru`, `httpx`, `boto3`, `pydantic-settings`, `twilio`, `python-multipart`
- **Edge cases**: Version pins should allow minor version updates (e.g., `>=0.100,<1` or `>=X.Y`). No overly strict pins that prevent pip resolution.

### FR-2: Dev extras group
- **What**: A `[project.optional-dependencies]` section named `dev` containing testing and linting tools.
- **Required dev deps**: `pytest`, `pytest-asyncio`, `httpx` (for TestClient), `ruff`, `pytest-mock`
- **Edge cases**: `httpx` appears in both runtime (for HTTP calls to external APIs) and dev (for FastAPI TestClient). It must be in runtime deps; listing it in dev extras too is acceptable but not required.

### FR-3: Project metadata
- **What**: `[project]` table with `name = "sehatsamjho"`, `version`, `requires-python = ">=3.11"`, and a `description`.
- **Inputs**: N/A
- **Outputs**: Valid PEP 621 metadata.

### FR-4: Ruff configuration
- **What**: `[tool.ruff]` section in `pyproject.toml` with `line-length = 100`.
- **Edge cases**: No other ruff overrides needed for prototype.

### FR-5: pytest configuration
- **What**: `[tool.pytest.ini_options]` section with `asyncio_mode = "auto"` and `testpaths = ["backend/tests"]`.

### FR-6: .env.example template
- **What**: A `.env.example` file listing every environment variable the application needs, with placeholder values and comments.
- **Required variables**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `BHASHINI_API_KEY`, `BHASHINI_USER_ID`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET`, `DATABASE_URL`, `REDIS_URL`
- **Edge cases**: No real secrets in the file. Each variable should have a descriptive comment.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `uv pip install -r pyproject.toml` succeeds with zero errors on Python 3.11+
- [ ] **Outcome 2**: `uv pip install -r pyproject.toml --extra dev` installs pytest, ruff, pytest-mock, pytest-asyncio
- [ ] **Outcome 3**: `python -c "import fastapi, uvicorn, sqlalchemy, asyncpg, aioredis, anthropic, openai, tenacity, loguru, httpx, boto3, pydantic_settings, twilio"` succeeds
- [ ] **Outcome 4**: `.env.example` contains all 12 required variables with placeholder values
- [ ] **Outcome 5**: `ruff check --config pyproject.toml` recognizes the config (line-length = 100)
- [ ] **Outcome 6**: `pytest --co --config pyproject.toml` picks up `asyncio_mode = "auto"` and `testpaths`

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_pyproject_exists**: Assert `pyproject.toml` exists at repo root
2. **test_pyproject_valid_toml**: Parse with `tomllib` — no syntax errors
3. **test_runtime_deps_present**: All 14 runtime deps listed in `[project.dependencies]`
4. **test_dev_extras_present**: All 5 dev deps listed in `[project.optional-dependencies.dev]`
5. **test_python_version_constraint**: `requires-python` is `">=3.11"`
6. **test_ruff_line_length**: `[tool.ruff].line-length` equals `100`
7. **test_pytest_asyncio_mode**: `[tool.pytest.ini_options].asyncio_mode` equals `"auto"`
8. **test_env_example_exists**: `.env.example` exists at repo root
9. **test_env_example_variables**: All 12 required env vars present in `.env.example`
10. **test_imports_succeed**: All runtime packages importable (validates installation)

### Mocking Strategy
- No external services to mock. These are static file validation tests.

### Coverage Expectation
- All FRs covered by at least one test. File existence, content parsing, and import validation.

---

## References
- roadmap.md Phase 1 — Project Setup
- CLAUDE.md — Environment section (uv, pyproject.toml as single source of truth)
