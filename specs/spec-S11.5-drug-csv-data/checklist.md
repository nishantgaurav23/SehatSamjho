# Checklist — Spec S11.5: Drug Database CSV (Data File)

## Phase 1: Setup & Dependencies
- [x] Verify S8.1 (Drug database CSV schema) is implemented and tests pass
- [x] Confirm existing `data/drugs/medicines.csv` has 66 entries with correct schema
- [x] Review existing S8.1 tests to ensure backward compatibility

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/data/test_s11_5_drug_csv_data.py`
- [x] Write 20 failing tests for data quality validation (1000+ rows, uniqueness, coverage, etc.)
- [x] Run `make local-test` — expect failures (Red) since CSV only has 66 rows

## Phase 3: Implementation
- [x] Research and curate additional Indian medicines to reach 1000 entries
- [x] Add entries across therapeutic classes: analgesic, antibiotic, antidiabetic, antihypertensive, antacid, cardiac, respiratory, dermatological, ophthalmic, neurological, psychiatric, endocrine, gastrointestinal, musculoskeletal, urological, hematological, immunological, oncological, antifungal, antiviral, etc.
- [x] Ensure all 7 columns populated for every new entry
- [x] Validate patient-friendly language in purpose_en (no jargon)
- [x] Preserve all original 66 S8.1 entries
- [x] Run tests — expect pass (Green)
- [x] Spot-check data quality (correct generic names, reasonable side effects, valid timing instructions)

## Phase 4: Integration
- [x] Verify existing S8.1 tests still pass (`backend/tests/data/test_drug_csv.py`)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 20 tangible outcome tests passing
- [x] CSV has >= 1000 rows with valid data
- [x] >= 20 therapeutic classes covered
- [x] No duplicate brand names
- [x] All purpose_en <= 200 chars
- [x] File is valid UTF-8, no BOM, parseable by csv module
- [x] Update roadmap.md status: pending -> done (when ready)
