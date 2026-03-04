# Checklist — Spec S7.3: User Prompt Builder

## Phase 1: Setup & Dependencies
- [x] Verify S7.1 (Anthropic client) is implemented and tests pass
- [x] Verify S2.4 (Pydantic models) is implemented and tests pass
- [x] Locate target file: `backend/app/services/translation.py`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_user_prompt.py`
- [x] Write 20 failing tests covering all FRs (import, signature, language header, metadata, PHI exclusion, medicine serialization, low-confidence marking, drug info, glossary, edge cases)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `_build_user_prompt()` in `backend/app/services/translation.py`
- [x] FR-1: Function signature with all parameters
- [x] FR-2: Language target header
- [x] FR-3: Prescription metadata section (no patient_name)
- [x] FR-4: Medicine entries with low-confidence marking
- [x] FR-5: Drug enrichment section (conditional)
- [x] FR-6: Glossary context section (conditional)
- [x] FR-7: PHI exclusion verified
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify function is accessible from module
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 8 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Pure function — no I/O, no side effects
- [x] patient_name never appears in output
- [x] Update roadmap.md status: pending -> done (when ready)
