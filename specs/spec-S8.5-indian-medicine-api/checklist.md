# Checklist — Spec S8.5: IndianMedicineDB API client

## Phase 1: Setup & Dependencies
- [x] Verify S8.3 (lookup_drug) is implemented and tests pass — 21/21
- [x] Locate target file: `backend/app/services/drug_lookup.py`
- [x] Verify httpx and tenacity are in pyproject.toml dependencies

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_indian_medicine_api.py`
- [x] Write 20 failing tests covering all FRs
- [x] Run tests — expect failures (Red) — 17/20 failed, 3 passed (stub)

## Phase 3: Implementation
- [x] Add `INDIANMEDICINEDB_BASE_URL` constant
- [x] Replace `_call_indianmedicinedb()` stub with real implementation
- [x] Add httpx async GET with `async with httpx.AsyncClient`
- [x] Add response field mapping (API fields → DrugInfo fields)
- [x] Add Tenacity retry (3 attempts, exponential backoff, 5xx/timeout/connect)
- [x] Add error handling (404, 4xx, 5xx, timeout, JSON, validation)
- [x] Add logging with request_id
- [x] Run tests — expect pass (Green) — 20/20 passed
- [x] Refactor if needed — clean

## Phase 4: Integration
- [x] Verify existing S8.3 tests still pass (lookup_drug calls _call_indianmedicinedb) — 21/21
- [x] Run `make local-lint` — clean
- [x] Run full test suite: `make local-test` — 848/848 passed

## Phase 5: Verification
- [x] All 7 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id
- [x] Update roadmap.md status: spec-written -> done
