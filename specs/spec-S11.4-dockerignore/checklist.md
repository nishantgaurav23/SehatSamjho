# Checklist — Spec S11.4: Docker Ignore Rules

## Phase 1: Setup & Dependencies
- [x] Verify no dependencies needed (standalone spec)
- [x] Confirm repo root is the correct location for `.dockerignore`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s11_4_dockerignore.py`
- [x] Write 20 failing tests for all FRs (static file validation)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Create `.dockerignore` at repository root
- [x] Add Python environment exclusions (`.venv`, `__pycache__`, `*.pyc`)
- [x] Add secrets exclusions (`.env`, `.env.*`)
- [x] Add VCS exclusions (`.git`)
- [x] Add documentation exclusions (`notebooks/`, `docs/`, `specs/`)
- [x] Add data exclusions (`data/drugs/`) with glossary override (`!data/glossary/`)
- [x] Add test/dev exclusions (`backend/tests/`, `.pytest_cache/`, `.ruff_cache/`)
- [x] Add Docker config exclusions (`Dockerfile`, `docker-compose*.yml`)
- [x] Add descriptive comments for each section
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `docker build` context excludes expected files (manual spot check)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 10 tangible outcomes checked
- [x] No secrets or sensitive paths included in build context
- [x] Glossary JSON files are NOT excluded (needed for seeding)
- [x] Update roadmap.md status: pending -> done (when ready)
