# Checklist — Spec S6.1: Glossary Data Files

## Phase 1: Setup & Dependencies
- [x] Verify GlossaryEntry schema exists in `backend/app/models/schemas.py` (S2.4)
- [x] Create directory `data/glossary/` if it does not exist

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/data/test_glossary_data.py`
- [x] Write tests for directory existence and file presence (3 tests)
- [x] Write tests for JSON validity per language (6 tests, parameterized)
- [x] Write tests for GlossaryEntry schema validation per language (6 tests, parameterized)
- [x] Write tests for minimum entry count per language (6 tests, parameterized)
- [x] Write tests for term uniqueness per language (6 tests, parameterized)
- [x] Write tests for cross-language term consistency (1 test)
- [x] Write tests for vernacular non-ASCII per language (6 tests, parameterized)
- [x] Write tests for term lowercase, explanation non-empty (parameterized)
- [x] Write test for vernacular differs across languages (1 test)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation (Data Files)
- [x] Create `data/glossary/hi.json` — Hindi (~20+ entries)
- [x] Create `data/glossary/ta.json` — Tamil (~20+ entries)
- [x] Create `data/glossary/te.json` — Telugu (~20+ entries)
- [x] Create `data/glossary/kn.json` — Kannada (~20+ entries)
- [x] Create `data/glossary/bn.json` — Bengali (~20+ entries)
- [x] Create `data/glossary/mr.json` — Marathi (~20+ entries)
- [x] Ensure all files share the same term set
- [x] Ensure all terms are lowercase English medical terms
- [x] Ensure vernacular fields use correct scripts per language
- [x] Run tests — expect pass (Green)

## Phase 4: Integration
- [x] No app wiring needed (data files only, consumed by S6.2)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All tangible outcomes checked
- [x] No hardcoded secrets (N/A for data files)
- [x] JSON files are well-formatted (consistent indentation)
- [x] Update roadmap.md status: spec-written -> done (when ready)
