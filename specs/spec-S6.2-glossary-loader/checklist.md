# Checklist — Spec S6.2: GlossaryLoader + load_glossary()

## Phase 1: Setup & Dependencies
- [x] Verify S2.2 (Async Redis client) is implemented and tests pass
- [x] Verify S6.1 (Glossary data files) is implemented and tests pass
- [x] Create target file: `backend/app/services/glossary.py`
- [x] Create test file: `backend/tests/services/test_glossary_loader.py`

## Phase 2: Tests First (TDD)
- [x] Write tests for constants & imports (tests 1–6)
- [x] Write tests for GlossaryLoader constructor (tests 7–9)
- [x] Write tests for _load_language_file (tests 10–16)
- [x] Write tests for load_all (tests 17–21)
- [x] Write tests for load_glossary convenience function (tests 22–23)
- [x] Write integration-style tests (tests 24–25)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement FR-1: GLOSSARY_DIR constant
- [x] Implement FR-2: GLOSSARY_REDIS_PREFIX constant
- [x] Implement FR-3: GlossaryLoader class + constructor
- [x] Implement FR-4: _load_language_file()
- [x] Implement FR-5: load_all()
- [x] Implement FR-6: load_glossary() convenience function
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Wire load_glossary() into app lifespan (main.py) if applicable (may defer to S11.7 seed)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 25 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes context (lang_code, count, file path)
- [x] Update roadmap.md status: pending -> done (when ready)
