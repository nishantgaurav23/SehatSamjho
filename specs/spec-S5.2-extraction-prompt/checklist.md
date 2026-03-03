# Checklist — Spec S5.2: Extraction Prompt

## Phase 1: Setup & Dependencies
- [x] Verify S5.1 (OpenAI client init) is implemented and passing
- [x] Locate target file: `backend/app/services/extraction.py`
- [x] Review `PrescriptionData` and `MedicineEntry` schemas in `backend/app/models/schemas.py`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_extraction_prompt.py`
- [x] Write 20 failing tests covering all FRs and tangible outcomes
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Add `EXTRACTION_SYSTEM_PROMPT` constant to `extraction.py`
- [x] Add `EXTRACTION_OUTPUT_SCHEMA` constant to `extraction.py`
- [x] Add `_build_extraction_prompt()` function to `extraction.py`
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify no import errors across the project
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 20 tests passing
- [x] All tangible outcomes checked
- [x] No hardcoded secrets
- [x] Constants are pure strings (no I/O at module level)
- [x] Update roadmap.md status: pending -> done (when ready)
