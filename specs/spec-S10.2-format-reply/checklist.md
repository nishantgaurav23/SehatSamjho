# Checklist — Spec S10.2: Format Reply

## Phase 1: Setup & Dependencies
- [x] Verify S10.1 (pipeline wiring) is implemented and tests pass
- [x] Verify S2.4 (Pydantic models) is implemented and tests pass
- [x] Locate target file: `backend/app/api/webhooks.py`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/api/test_format_reply.py`
- [x] Write tests for FR-1: importable, signature, sync function
- [x] Write tests for FR-2: greeting section present
- [x] Write tests for FR-3: per-medicine cards (name, dosage, frequency, duration, missing fields, summaries)
- [x] Write tests for FR-4: low-confidence warnings (< 0.7, >= 0.7, boundary)
- [x] Write tests for FR-5: disclaimer at end
- [x] Write tests for FR-6: 1600-char limit and truncation
- [x] Write tests for edge cases: empty medicines, no PHI
- [x] Write test for FR-7: pipeline wiring uses `_format_reply`
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `_format_reply()` — greeting section (FR-2)
- [x] Implement per-medicine card builder (FR-3)
- [x] Implement low-confidence warning logic (FR-4)
- [x] Implement disclaimer section (FR-5)
- [x] Implement 1600-char truncation logic (FR-6)
- [x] Handle empty medicines edge case (FR-1 / FR-3)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Wire `_format_reply()` into `_run_pipeline()` (FR-7)
- [x] Verify existing S10.1 pipeline tests still pass
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 20 tangible outcome tests pass
- [x] No hardcoded secrets
- [x] No PHI (patient_name, doctor_name) in formatted output
- [x] Logging includes request_id where applicable
- [x] Output never exceeds 1600 characters
- [x] Update roadmap.md status: spec-written -> done (when ready)
