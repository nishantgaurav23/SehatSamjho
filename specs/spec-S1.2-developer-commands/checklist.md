# Checklist — Spec S1.2: Developer Commands

## Phase 1: Setup & Dependencies
- [x] Verify S1.2 has no spec dependencies (standalone)
- [x] Confirm project root is the correct location for Makefile
- [x] No new imports/dependencies needed in pyproject.toml

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s1_2_developer_commands.py`
- [x] Write test: `test_makefile_exists`
- [x] Write test: `test_makefile_has_all_targets` (11 targets)
- [x] Write test: `test_makefile_phony_declarations`
- [x] Write test: `test_makefile_venv_target_uses_python311`
- [x] Write test: `test_makefile_install_uses_uv`
- [x] Write test: `test_makefile_install_dev_uses_uv`
- [x] Write test: `test_makefile_local_dev_uses_uvicorn`
- [x] Write test: `test_makefile_local_test_uses_pytest`
- [x] Write test: `test_makefile_local_lint_uses_ruff`
- [x] Write test: `test_makefile_local_migrate_uses_alembic`
- [x] Write test: `test_makefile_dev_target_uses_docker_compose`
- [x] Write test: `test_makefile_test_target_uses_docker`
- [x] Write test: `test_makefile_migrate_target_uses_docker`
- [x] Write test: `test_makefile_seed_target_defined`
- [x] Write test: `test_makefile_uses_tabs`
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Create `Makefile` at project root
- [x] Implement `venv` target — `python3.11 -m venv .venv`
- [x] Implement `install` target — `uv pip install -r pyproject.toml`
- [x] Implement `install-dev` target — `uv pip install -r pyproject.toml --extra dev`
- [x] Implement `local-dev` target — `cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- [x] Implement `local-test` target — `cd backend && python -m pytest tests/ -v --tb=short`
- [x] Implement `local-lint` target — `ruff check backend/ && ruff format --check backend/`
- [x] Implement `local-migrate` target — `cd backend && alembic upgrade head`
- [x] Implement `dev` target — `docker compose up --build`
- [x] Implement `test` target — `docker compose exec app python -m pytest tests/ -v --tb=short`
- [x] Implement `migrate` target — `docker compose exec app alembic upgrade head`
- [x] Implement `seed` target — seed script execution
- [x] Add `.PHONY` declarations for all targets
- [x] Verify tab indentation (not spaces)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `make venv` works (creates .venv)
- [x] Verify `make install` works (installs deps)
- [x] Verify `make install-dev` works (installs dev deps)
- [x] Verify `make local-test` runs test suite
- [x] Verify `make local-lint` runs ruff
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All tangible outcomes checked (14 items)
- [x] No hardcoded secrets in Makefile
- [x] Makefile uses consistent formatting
- [x] Update roadmap.md status: spec-written -> done
