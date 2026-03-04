# Checklist — Spec S7.2: System Prompt

## Phase 1: Setup & Dependencies
- [x] Verify S7.1 (Anthropic client) is implemented and tests pass
- [x] Locate target file: `backend/app/services/translation.py`
- [x] No new imports/dependencies needed (pure string formatting)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_system_prompt.py`
- [x] Write 20 failing tests covering:
  - Importability of `TRANSLATION_SYSTEM_PROMPT` and `_build_system_prompt`
  - Type and length checks on the constant
  - Placeholder presence in template
  - `_build_system_prompt` signature (default arg)
  - Empty glossary → no glossary section
  - Non-empty glossary → glossary section injected
  - None glossary → no error, no glossary section
  - Whitespace-only glossary → no glossary section
  - Persona rule present
  - Drug name preservation rule present
  - No-advice rule present
  - Confidence flagging rule present
  - Word limit rule present
  - Disclaimer rule present
  - No remaining `{` / `}` placeholders in output
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Add `TRANSLATION_SYSTEM_PROMPT` constant to `translation.py` with all 6 rules and `{glossary_context}` placeholder
- [x] Implement `_build_system_prompt(glossary_context: str = "")` — inject glossary or strip section
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] No router/dependency/lifespan wiring needed (internal function)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 6 tangible outcomes checked
- [x] No hardcoded secrets in prompt
- [x] No PHI in prompt template
- [x] Update roadmap.md status: pending → done (when ready)
