# Checklist — Spec S3.2: Parse Language Selection

## Phase 1: Setup & Dependencies
- [x] Verify S3.1 is implemented (SUPPORTED_LANGUAGES, TOP_LANGUAGES in whatsapp.py)
- [x] Locate target file: `backend/app/services/whatsapp.py`
- [x] No new dependencies needed (pure function, no external packages)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_parse_language.py`
- [x] test_parse_numeric_valid — numbers 1–8 map to TOP_LANGUAGES
- [x] test_parse_numeric_out_of_range — "0", "9", "99", "-1" return None
- [x] test_parse_language_code_valid — all 22 codes return (name, code)
- [x] test_parse_language_code_case_insensitive — "HI", "Ta", "KOK" match
- [x] test_parse_language_name_english — "Hindi", "tamil", "BENGALI" match
- [x] test_parse_language_name_display — native display_name matches
- [x] test_parse_whitespace_stripping — "  hi  ", " 1 " work
- [x] test_parse_empty_string — "" returns None
- [x] test_parse_none_like — whitespace-only returns None
- [x] test_parse_unrecognised_input — random text returns None
- [x] test_parse_numeric_not_a_number — "abc", "1.5" return None
- [x] test_parse_return_type_tuple — valid match returns 2-tuple
- [x] test_parse_return_type_none — invalid match returns None
- [x] test_parse_code_priority — "hi" matches code, not treated as greeting
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `parse_language_selection()` in whatsapp.py
  - [x] Strip whitespace from input
  - [x] Handle empty/None-like input → return None
  - [x] Try numeric match (1–8 → TOP_LANGUAGES index)
  - [x] Try language code match (lowercase → SUPPORTED_LANGUAGES key)
  - [x] Try language name match (case-insensitive English name)
  - [x] Try display_name match (native script)
  - [x] Return None if no match
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] No router/dependency wiring needed (pure utility function)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All tangible outcomes checked
- [x] No hardcoded secrets
- [x] Pure function — no logging or external calls needed
- [x] Update roadmap.md status: pending -> done (when ready)
