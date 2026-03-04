# Checklist — Spec S11.6: Glossary Data Files (Data Files)

## Phase 1: Setup & Dependencies
- [x] Verify S6.1 (Glossary data files schema) is implemented and tests pass
- [x] Confirm existing 6 glossary JSON files exist in `data/glossary/`
- [x] Confirm existing S6.1 tests pass (53 tests in `backend/tests/data/test_glossary_data.py`)
- [x] Note current entry count per file (25 entries each)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/data/test_s11_6_glossary_data_files.py`
- [x] Write failing tests for FR-1 (>= 100 entries per file)
- [x] Write failing tests for FR-2 (all fields non-empty)
- [x] Write failing tests for FR-3 (original 25 entries preserved)
- [x] Write failing tests for FR-4 (unique terms per file)
- [x] Write failing tests for FR-5 (consistent term set across languages)
- [x] Write failing tests for FR-6 (terms all lowercase)
- [x] Write failing tests for FR-7 (medical category coverage)
- [x] Write failing tests for FR-8 (vernacular script characters)
- [x] Write failing tests for FR-9 (explanation max length)
- [x] Write failing tests for FR-10 (valid JSON/UTF-8)
- [x] Run make local-test — expect failures (Red) — 7 failed, 73 passed

## Phase 3: Implementation
- [x] Curate 75+ additional medical terms covering: conditions, medication instructions, body parts, lab terms, procedures, symptoms, drug classes, dosage forms, abbreviations
- [x] Expand `data/glossary/hi.json` to >= 100 entries with Hindi vernacular
- [x] Expand `data/glossary/ta.json` to >= 100 entries with Tamil vernacular
- [x] Expand `data/glossary/te.json` to >= 100 entries with Telugu vernacular
- [x] Expand `data/glossary/kn.json` to >= 100 entries with Kannada vernacular
- [x] Expand `data/glossary/bn.json` to >= 100 entries with Bengali vernacular
- [x] Expand `data/glossary/mr.json` to >= 100 entries with Marathi vernacular
- [x] Ensure all original 25 entries are preserved in each file
- [x] Verify consistent term set across all 6 files
- [x] Run tests — expect pass (Green) — 80/80 passed
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify existing S6.1 tests still pass (53 tests)
- [x] Run make local-lint
- [x] Run full test suite: make local-test — 1244 passed (updated glossary_loader integration test)

## Phase 5: Verification
- [x] All tangible outcomes checked
- [x] No hardcoded secrets
- [x] Files are valid UTF-8 JSON
- [x] Vernacular entries use correct language scripts
- [x] Update roadmap.md status: spec-written → done
