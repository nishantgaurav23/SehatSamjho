# Checklist — Spec S1.1: Dependency Declaration

## Phase 1: Setup & Dependencies
- [x] No upstream dependencies — this is the first spec
- [x] Verify repo root exists and is a git repository
- [x] Confirm Python 3.11+ available (`python --version`)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s1_1_dependency_declaration.py`
- [x] Write `test_pyproject_exists` — assert file at repo root
- [x] Write `test_pyproject_valid_toml` — parse with tomllib
- [x] Write `test_runtime_deps_present` — check all 14 runtime deps
- [x] Write `test_dev_extras_present` — check all 5 dev deps
- [x] Write `test_python_version_constraint` — requires-python >= 3.11
- [x] Write `test_ruff_line_length` — line-length = 100
- [x] Write `test_pytest_asyncio_mode` — asyncio_mode = "auto"
- [x] Write `test_env_example_exists` — .env.example at root
- [x] Write `test_env_example_variables` — all 12 env vars present
- [x] Write `test_imports_succeed` — all runtime packages importable
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Create/update `pyproject.toml` with project metadata (name, version, requires-python)
- [x] Add all 14 runtime dependencies to `[project.dependencies]` (note: `aioredis` replaced with `redis>=4.5` — aioredis is unmaintained and broken on Python 3.11+; `redis.asyncio` is the successor)
- [x] Add dev extras group with 5 dev dependencies
- [x] Add `[tool.ruff]` section with `line-length = 100`
- [x] Add `[tool.pytest.ini_options]` with `asyncio_mode = "auto"`, `testpaths`
- [x] Create `.env.example` with all 12 environment variables + comments
- [x] Run `uv pip install -r pyproject.toml` — verify success
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] N/A — Makefile does not exist yet (S1.2)
- [x] N/A — Makefile does not exist yet (S1.2)
- [x] Verified ruff picks up config via `ruff check --config pyproject.toml`
- [x] Full test suite: 22/22 passing

## Phase 5: Verification
- [x] All 6 tangible outcomes checked
- [x] No hardcoded secrets in any file
- [x] `.env.example` has placeholder values only (no real keys)
- [x] `pyproject.toml` is valid PEP 621
- [x] Update roadmap.md status: spec-written -> done
