# Checklist — Spec S10.1: Pipeline Wiring

## Phase 1: Setup & Dependencies
- [x] Verify dependencies (S4.5, S5.4, S6.3, S6.4, S7.4, S8.4, S9.4) are implemented
- [x] Locate target file: `backend/app/api/webhooks.py` (existing `_run_pipeline()` placeholder)
- [x] No new pyproject.toml dependencies needed (all services already imported in their modules)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/api/test_pipeline_wiring.py`
- [x] Write 20 failing tests covering all FRs (pipeline sequence, request_id threading, latency, confidence, logging, session cleanup, audio fallback)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Add imports for extraction, drug_lookup, glossary, translation, tts services to webhooks.py
- [x] Add import for `send_audio_message_with_fallback` from whatsapp
- [x] Add import for `AsyncSessionLocal` from database module
- [x] Add `import time` for latency tracking
- [x] Implement FR-1: Full pipeline sequence in `_run_pipeline()`
- [x] Implement FR-2: Thread request_id to all service calls
- [x] Implement FR-3: Loguru context binding for each step
- [x] Implement FR-4: Latency tracking with `time.monotonic()`
- [x] Implement FR-5: Confidence average calculation
- [x] Implement FR-6: Call `_log_interaction()` on success
- [x] Implement FR-7: Acquire DB session via `AsyncSessionLocal()`
- [x] Implement FR-8: Session cleanup in finally block
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `_handle_image_state()` still calls `_run_pipeline()` correctly
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 8 tangible outcomes checked
- [x] No hardcoded secrets
- [x] Logging includes request_id in all pipeline log messages
- [x] No PHI logged (no raw phone numbers, no image content, no extracted text in logs)
- [x] Update roadmap.md status: spec-written -> done (when ready)
