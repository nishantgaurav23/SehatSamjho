# Checklist — Spec S1.5: Twilio HMAC Verification

## Phase 1: Setup & Dependencies
- [x] Verify S1.3 (pydantic-settings) is implemented and tests pass
- [x] Create target file: `backend/app/core/security.py`
- [x] Confirm `twilio` package is in pyproject.toml (added in S1.1)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/core/test_security.py`
- [x] Write test_valid_signature_passes
- [x] Write test_invalid_signature_returns_403
- [x] Write test_missing_signature_header_returns_403
- [x] Write test_empty_signature_returns_403
- [x] Write test_uses_twilio_auth_token_from_settings
- [x] Write test_form_body_included_in_validation
- [x] Write test_url_reconstruction_direct
- [x] Write test_url_reconstruction_behind_proxy
- [x] Write test_dependency_is_async
- [x] Write test_valid_signature_with_empty_body
- [x] Run make local-test — expect failures (Red)

## Phase 3: Implementation
- [x] Implement FR-1 — RequestValidator init with settings.TWILIO_AUTH_TOKEN
- [x] Implement FR-4 — URL reconstruction (direct + proxy)
- [x] Implement FR-2 — validate_twilio_signature async function
- [x] Implement FR-3 — Export as FastAPI Depends()-compatible dependency
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify security.py is importable from backend.app.core.security
- [x] Run make local-lint
- [x] Run full test suite: make local-test

## Phase 5: Verification
- [x] All 10 tests pass
- [x] No hardcoded secrets (auth token from settings only)
- [x] Logging includes relevant context on 403 rejections
- [x] Function is async def (FastAPI async dependency compatible)
- [x] Update roadmap.md status: spec-written -> done
