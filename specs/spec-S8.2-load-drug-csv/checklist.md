# Checklist — Spec S8.2: Load Drug CSV

## Phase 1: Setup & Dependencies
- [x] Verify S2.2 (Async Redis) is implemented and tests pass
- [x] Verify S8.1 (Drug database CSV) is implemented and tests pass
- [x] Create or locate target file: `backend/app/services/drug_lookup.py`
- [x] No new imports/dependencies needed (csv is stdlib, redis already in pyproject.toml)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_load_drug_csv.py`
- [x] Write 4 constant tests (DRUG_CSV_PATH, DRUG_REDIS_PREFIX)
- [x] Write 3 constructor tests (DrugCSVLoader)
- [x] Write 9 _load_csv() tests (reads, stores, normalizes, skips, errors)
- [x] Write 2 load_all() tests (delegates, logs)
- [x] Write 2 load_drug_csv() tests (async, delegates)
- [x] Run `make local-test` — expect 20 failures (Red)

## Phase 3: Implementation
- [x] Implement FR-1 — DRUG_CSV_PATH constant
- [x] Implement FR-2 — DRUG_REDIS_PREFIX constant
- [x] Implement FR-3 — DrugCSVLoader class constructor
- [x] Implement FR-4 — DrugCSVLoader._load_csv() method
- [x] Implement FR-5 — DrugCSVLoader.load_all() method
- [x] Implement FR-6 — load_drug_csv() module-level function
- [x] Run tests — expect 20 pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify drug_lookup.py is importable from backend.app.services
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 7 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes context (entry count, file path) but no PHI
- [x] Update roadmap.md status: pending -> done (when ready)
