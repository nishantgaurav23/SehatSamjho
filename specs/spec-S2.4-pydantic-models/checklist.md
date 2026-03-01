# Checklist — Spec S2.4: Pydantic Models

## Phase 1: Setup & Dependencies
- [x] Verify S1.1 (dependency declaration) is implemented — pydantic available
- [x] Create target directory: `backend/app/models/`
- [x] Create `backend/app/models/__init__.py`
- [x] Create `backend/app/models/schemas.py`

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/models/test_schemas.py`
- [x] Create `backend/tests/models/__init__.py`
- [x] Write tests for SessionStatus enum (2 tests)
- [x] Write tests for MedicineEntry (4 tests)
- [x] Write tests for PrescriptionData (4 tests)
- [x] Write tests for DrugInfo (3 tests)
- [x] Write tests for GlossaryEntry (2 tests)
- [x] Write tests for TranslationResult (3 tests)
- [x] Write tests for WebhookPayload (5 tests)
- [x] Write tests for SessionState (4 tests)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement SessionStatus enum
- [x] Implement MedicineEntry model
- [x] Implement PrescriptionData model
- [x] Implement DrugInfo model
- [x] Implement GlossaryEntry model
- [x] Implement TranslationResult model
- [x] Implement WebhookPayload model
- [x] Implement SessionState model
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify all models importable from `backend.app.models.schemas`
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 7 tangible outcomes checked
- [x] No hardcoded secrets
- [x] All models use Pydantic v2 conventions
- [x] JSON round-trip works for all models
- [x] Update roadmap.md status: spec-written -> done
