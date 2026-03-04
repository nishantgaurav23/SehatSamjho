# Checklist — Spec S7.1: Anthropic Async Client + Prompt Templates

## Phase 1: Setup & Dependencies
- [x] Verify S1.3 (pydantic-settings config) is implemented and passing
- [x] Create target file: `backend/app/services/translation.py`
- [x] Verify `anthropic` is already in pyproject.toml dependencies (from S1.1)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_anthropic_client.py`
- [x] Write test_translation_module_importable
- [x] Write test_get_client_returns_async_anthropic
- [x] Write test_get_client_singleton
- [x] Write test_get_client_uses_api_key
- [x] Write test_reset_client_clears_cache
- [x] Write test_get_client_lazy_settings_import
- [x] Write test_get_client_creates_client_with_correct_args
- [x] Write test_module_has_docstring
- [x] Write test_module_exposes_expected_names
- [x] Write test_get_client_after_reset_uses_fresh_settings
- [x] Write test_claude_model_constant
- [x] Write test_translation_max_tokens_constant
- [x] Write test_translation_temperature_constant
- [x] Run make local-test — expect failures (Red)

## Phase 3: Implementation
- [x] Implement module docstring + imports (anthropic, loguru)
- [x] Implement `_client` module-level variable
- [x] Implement `_get_client()` with lazy settings import + singleton caching
- [x] Implement `_reset_client()` to clear cached client
- [x] Implement `CLAUDE_MODEL` constant (`"claude-sonnet-4-6"`)
- [x] Implement `TRANSLATION_MAX_TOKENS` constant (`1024`)
- [x] Implement `TRANSLATION_TEMPERATURE` constant (`0.3`)
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify module is importable from project root
- [x] Run make local-lint
- [x] Run full test suite: make local-test

## Phase 5: Verification
- [x] All 13 tangible outcomes checked
- [x] No hardcoded secrets (API key from settings only)
- [x] Lazy import pattern confirmed (no module-level settings)
- [x] Singleton pattern confirmed
- [x] Update roadmap.md status: spec-written → done
