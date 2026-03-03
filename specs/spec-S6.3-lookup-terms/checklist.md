# Checklist — Spec S6.3: lookup_terms()

## Phase 1: Setup & Dependencies
- [x] Verify S6.2 (GlossaryLoader + load_glossary()) is implemented and passing
- [x] Verify S2.4 (Pydantic models — GlossaryEntry) is implemented and passing
- [x] Locate target file: `backend/app/services/glossary.py`
- [x] Confirm `GLOSSARY_REDIS_PREFIX` constant exists from S6.2

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/services/test_lookup_terms.py`
- [x] Write tests 1–3: imports, async check, signature
- [x] Write tests 4–6: empty/no-op cases
- [x] Write tests 7–9: term normalization
- [x] Write tests 10–12: Redis interaction (HMGET)
- [x] Write tests 13–17: happy path (matches, partial, ordering)
- [x] Write tests 18–20: error resilience
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `lookup_terms()` in `backend/app/services/glossary.py`
  - [x] FR-1: Function signature with type hints
  - [x] FR-2: Term normalization (lowercase, strip, dedup)
  - [x] FR-3: Batch HMGET on `glossary:{lang_code}`
  - [x] FR-4: Error resilience (Redis errors, JSON errors, Pydantic errors)
  - [x] FR-5: Maintain input order in results
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `lookup_terms` is importable from `backend.app.services.glossary`
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 20 tests passing
- [x] All tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes language_code context
- [x] Update roadmap.md status: pending -> done (when ready)
