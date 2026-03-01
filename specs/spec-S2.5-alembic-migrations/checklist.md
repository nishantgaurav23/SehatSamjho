# Checklist — Spec S2.5: Alembic Migrations Setup

## Phase 1: Setup & Dependencies
- [x] Verify S2.1 (async SQLAlchemy engine) is implemented and tests pass
- [x] Verify S2.3 (interaction_log table model) is implemented and tests pass
- [x] Add `alembic>=1.12` to `pyproject.toml` runtime dependencies
- [x] Run `uv pip install -r pyproject.toml` to install Alembic

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s2_5_alembic_migrations.py`
- [x] Write 20 failing tests covering all FRs (static file validation)
- [x] Run `make local-test` — expect failures (Red) — 18 failed, 2 passed

## Phase 3: Implementation
- [x] Create `backend/alembic.ini` with script_location, prepend_sys_path, empty sqlalchemy.url (FR-1)
- [x] Create `backend/alembic/env.py` with async engine, Base import, models import (FR-2)
- [x] Create `backend/alembic/script.py.mako` standard template (FR-3)
- [x] Create `backend/alembic/versions/` directory
- [x] Generate initial migration for interaction_log table (FR-4)
- [x] Verify migration upgrade() creates table with all 9 columns
- [x] Verify migration downgrade() drops interaction_log table
- [x] Run tests — expect pass (Green) — 20/20 passed
- [x] Refactor if needed — no refactoring necessary

## Phase 4: Integration
- [x] Verify `make local-migrate` can parse alembic.ini without import errors
- [x] Run `make local-lint` — all checks passed, 32 files formatted
- [x] Run full test suite: `make local-test` — 162/162 passed

## Phase 5: Verification
- [x] All 7 tangible outcomes checked
- [x] No hardcoded database URLs or secrets in any file
- [x] alembic.ini sqlalchemy.url is empty/placeholder
- [x] env.py reads DATABASE_URL from settings at runtime
- [x] Update roadmap.md status: spec-written → done
