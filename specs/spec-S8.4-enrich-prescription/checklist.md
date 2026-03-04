# Checklist — Spec S8.4: enrich prescription

## Phase 1: Setup & Dependencies
- [x] Verify S8.3 (lookup_drug) is implemented and tests pass
- [x] Verify S2.4 (Pydantic models) is implemented and tests pass
- [x] Locate target file: `backend/app/services/drug_lookup.py`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_enrich_prescription.py`
- [x] Write 20 failing tests covering all FRs
- [x] Run `make local-test` — expect failures (Red) — 20/20 failed

## Phase 3: Implementation
- [x] Implement `enrich_prescription()` — async, uses asyncio.gather
- [x] Handle empty medicines list (early return `[]`)
- [x] Handle gather exceptions (return list of Nones)
- [x] Add logging (start count, completion hits/misses, request_id)
- [x] Run tests — expect pass (Green) — 20/20 passed
- [x] Refactor if needed — clean, no changes needed

## Phase 4: Integration
- [x] Verify function is importable from `backend.app.services.drug_lookup`
- [x] Run `make local-lint` — clean
- [x] Run full test suite: `make local-test` — 808/808 passed

## Phase 5: Verification
- [x] All 6 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id
- [x] Update roadmap.md status: spec-written -> done
