# Checklist — Spec S8.1: Drug Database CSV

## Phase 1: Setup & Dependencies
- [x] Verify no code dependencies (standalone data file)
- [x] Create directory `data/drugs/` if it doesn't exist
- [x] Confirm CSV format and column requirements from spec

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/data/test_drug_csv.py`
- [x] Write tests for file existence and encoding (tests 1-2)
- [x] Write tests for header validation (tests 3-4)
- [x] Write tests for row count and empty rows (tests 5, 17)
- [x] Write tests for required field validation (tests 6-13)
- [x] Write tests for data quality (tests 14-16, 18-20)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Create `data/drugs/medicines.csv` with correct header row
- [x] Populate with ~50+ most-prescribed Indian medicines
- [x] Include common categories: analgesics, antibiotics, antihypertensives, antidiabetics, antacids, vitamins, etc.
- [x] Ensure all required fields are non-empty
- [x] Ensure known_interactions column exists (may be empty for some rows)
- [x] Verify no duplicate brand names (case-insensitive)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify CSV is accessible from project root path `data/drugs/medicines.csv`
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All tangible outcomes checked
- [x] No hardcoded secrets (N/A for data file)
- [x] CSV data is from public domain / non-proprietary sources
- [x] Update roadmap.md status: pending -> done (when ready)
