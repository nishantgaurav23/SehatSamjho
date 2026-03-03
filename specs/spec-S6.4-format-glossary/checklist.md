# Checklist — Spec S6.4: format glossary context

## Phase 1: Setup & Dependencies
- [x] Verify S6.3 (lookup_terms) is implemented and passing
- [x] Locate target file: `backend/app/services/glossary.py`
- [x] No new imports/dependencies needed (pure function)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_format_glossary.py`
- [x] Write 20 failing tests for FR-1 through FR-5
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `format_glossary_context()` — line formatting (FR-2)
- [x] Implement block structure with header/footer (FR-3)
- [x] Implement token budget truncation (FR-4)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Function is exported from `backend.app.services.glossary`
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test` — 654 passed

## Phase 5: Verification
- [x] All 6 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Pure function (no async, no I/O, no side effects)
- [x] Update roadmap.md status: pending -> done (when ready)
