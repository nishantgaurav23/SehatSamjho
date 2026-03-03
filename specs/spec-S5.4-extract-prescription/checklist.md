# Checklist — Spec S5.4: extract prescription

## Phase 1: Setup & Dependencies
- [x] Verify S5.3 (GPT-4O Vision call) is implemented and tests pass
- [x] Verify S2.4 (Pydantic models) is implemented and tests pass
- [x] Locate target file: `backend/app/services/extraction.py`

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/services/test_extract_prescription.py`
- [x] Write tests 1–3: importable, async, signature
- [x] Write tests 4–6: happy path, medicines, content_type forwarding
- [x] Write tests 7–8: empty URL, whitespace URL validation
- [x] Write tests 9–10: invalid JSON, empty response
- [x] Write tests 11–12: code fence stripping (with/without lang tag)
- [x] Write tests 13–14: validation error, missing required field
- [x] Write tests 15–18: logging (start, completion, error, no PHI)
- [x] Write tests 19–20: GPT-4O call verification, error propagation
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Add `import json` to extraction.py
- [x] Implement `extract_prescription()` — URL validation (FR-2)
- [x] Implement JSON parsing with code fence stripping (FR-4)
- [x] Implement PrescriptionData validation (FR-5)
- [x] Add logging at start, completion, and error points (FR-6)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `extract_prescription` is importable as public API
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 10 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Image URLs never logged (PHI safety)
- [x] Logging includes contextual info (doc_type, medicine count)
- [x] Update roadmap.md status: spec-written -> done
