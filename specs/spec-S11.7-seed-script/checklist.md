# Checklist — Spec S11.7: Seed Script

## Phase 1: Setup & Dependencies
- [x] Verify S8.2 (load_drug_csv) is implemented and tests pass
- [x] Verify S6.2 (load_glossary) is implemented and tests pass
- [x] Verify S2.5 (Alembic migrations) is implemented and tests pass
- [x] Create `backend/scripts/` directory if needed
- [x] Create `backend/scripts/__init__.py` package marker

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s11_7_seed_script.py`
- [x] Write failing tests for FR-1 (entry point, importable, main async)
- [x] Write failing tests for FR-2 (Redis connection management)
- [x] Write failing tests for FR-3 (load_drug_csv call + logging)
- [x] Write failing tests for FR-4 (load_glossary call + logging)
- [x] Write failing tests for FR-5 (summary logging + elapsed time)
- [x] Write failing tests for FR-6 (idempotent — covered by Redis HSET semantics)
- [x] Write failing tests for FR-7 (Makefile local-seed target)
- [x] Write tests for error handling (exit codes, partial failure, connection failure)
- [x] Run make local-test — expect failures (Red)

## Phase 3: Implementation
- [x] Create `backend/scripts/__init__.py`
- [x] Implement `backend/scripts/seed.py` — main() async function
- [x] FR-1: asyncio.run(main()) entry point
- [x] FR-2: Redis connection from settings.REDIS_URL, close in finally
- [x] FR-3: Call load_drug_csv(redis_client), log count
- [x] FR-4: Call load_glossary(redis_client), log per-language counts
- [x] FR-5: Log summary with totals and elapsed time
- [x] FR-7: Add `local-seed` target to Makefile
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify existing `make seed` Docker target is compatible
- [x] Run make local-lint
- [x] Run full test suite: make local-test

## Phase 5: Verification
- [x] All 9 tangible outcomes checked
- [x] No hardcoded secrets (uses settings.REDIS_URL)
- [x] Logging uses Loguru
- [x] Exit code 0 on success, 1 on failure
- [x] Redis connection closed in all code paths
- [x] Update roadmap.md status: spec-written → done (when ready)
