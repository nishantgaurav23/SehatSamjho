# Checklist — Spec S5.1: OpenAI Async Client Init

## Phase 1: Setup & Dependencies
- [x] Verify S1.3 (pydantic-settings config) is implemented and passing
- [x] Verify S2.4 (Pydantic models) is implemented and passing
- [x] Create target file: `backend/app/services/extraction.py`
- [x] Confirm `openai` package is in `pyproject.toml` dependencies (from S1.1)

## Phase 2: Tests First (TDD)
- [x] Create test file: `backend/tests/services/test_openai_client.py`
- [x] Write test_extraction_module_importable
- [x] Write test_get_client_returns_async_openai
- [x] Write test_get_client_singleton
- [x] Write test_get_client_uses_api_key
- [x] Write test_reset_client_clears_cache
- [x] Write test_get_client_lazy_settings_import
- [x] Write test_get_client_creates_client_with_correct_args
- [x] Write test_module_has_docstring
- [x] Write test_module_exposes_expected_names
- [x] Write test_get_client_after_reset_uses_fresh_settings
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement module docstring and imports (openai, loguru)
- [x] Implement `_client` module-level variable (initially `None`)
- [x] Implement `_get_client()` with lazy settings import and singleton caching
- [x] Implement `_reset_client()` to clear the cached client
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `extraction.py` is importable from `backend.app.services.extraction`
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 10 tangible outcomes checked
- [x] No hardcoded API keys (uses settings.OPENAI_API_KEY)
- [x] Lazy import pattern confirmed (no module-level settings import)
- [x] Singleton pattern works correctly
- [x] Update roadmap.md status: spec-written -> done (when implemented)
