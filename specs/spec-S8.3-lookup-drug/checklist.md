# Checklist — Spec S8.3: lookup drug

## Phase 1: Setup & Dependencies
- [x] Verify S8.2 (load_drug_csv) is implemented and tests pass
- [x] Verify S2.4 (DrugInfo Pydantic model) is implemented
- [x] Locate target file: `backend/app/services/drug_lookup.py`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_lookup_drug.py`
- [x] Write 20 failing tests covering all FRs
- [x] Run make local-test — expect failures (Red)

## Phase 3: Implementation
- [x] Implement FR-1 — `_normalize_drug_name()` helper
- [x] Implement FR-4 — `DRUG_CACHE_TTL_SECONDS` constant
- [x] Implement FR-5 — `_call_indianmedicinedb()` stub
- [x] Implement FR-2 — `lookup_drug()` Redis hit path
- [x] Implement FR-3 — `lookup_drug()` API fallback + cache-on-hit
- [x] Implement FR-6 — Loguru logging with request_id
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Ensure `lookup_drug()` is importable from `backend.app.services.drug_lookup`
- [x] Run make local-lint
- [x] Run full test suite: make local-test (768 passed)

## Phase 5: Verification
- [x] All 6 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id where applicable
- [x] PHI-safe: no patient data logged
- [x] Update roadmap.md status: pending -> done (when ready)
