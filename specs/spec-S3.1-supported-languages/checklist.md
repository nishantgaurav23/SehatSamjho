# Checklist — Spec S3.1: Supported Languages

## Phase 1: Setup & Dependencies
- [x] Verify S2.4 (Pydantic models) is implemented and passing
- [x] Locate target file: `backend/app/services/whatsapp.py`
- [x] No new imports/dependencies needed (pure Python dicts + functions)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_supported_languages.py`
- [x] Write 20 failing tests covering all FRs:
  - SUPPORTED_LANGUAGES: count, keys, values, required fields, no empty values
  - TOP_LANGUAGES: count, subset of supported, order
  - get_language_name(): valid, invalid, empty, case-insensitive
  - is_supported_language(): valid, invalid, empty, case-insensitive
  - Bhashini code consistency, display name non-ASCII
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `SUPPORTED_LANGUAGES` dict (22 entries) in `whatsapp.py`
- [x] Implement `TOP_LANGUAGES` list (8 entries) in `whatsapp.py`
- [x] Implement `get_language_name(code)` in `whatsapp.py`
- [x] Implement `is_supported_language(code)` in `whatsapp.py`
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Ensure whatsapp.py module is importable from app package
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 5 tangible outcomes verified
- [x] No hardcoded secrets
- [x] No external service calls (pure data)
- [x] Update roadmap.md status: spec-written → done (when implementation complete)
