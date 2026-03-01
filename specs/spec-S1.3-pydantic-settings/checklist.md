# Checklist — Spec S1.3: pydantic-settings config

## Phase 1: Setup & Dependencies
- [x] Verify S1.1 is implemented (`pydantic-settings` in `pyproject.toml`)
- [x] Create target file: `backend/app/core/config.py`
- [x] Ensure `backend/app/core/__init__.py` exists

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/core/test_config.py`
- [x] Write `test_settings_class_exists`
- [x] Write `test_settings_inherits_base_settings`
- [x] Write `test_settings_has_all_fields`
- [x] Write `test_settings_loads_from_env`
- [x] Write `test_settings_required_fields_missing`
- [x] Write `test_settings_s3_bucket_default`
- [x] Write `test_settings_database_url_default`
- [x] Write `test_settings_redis_url_default`
- [x] Write `test_settings_singleton_exported`
- [x] Write `test_settings_env_file_configured`
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `Settings(BaseSettings)` with all 12 fields
- [x] Add `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")`
- [x] Add module-level `settings = Settings()` singleton
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `from backend.app.core.config import settings` works from project root
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 10 tangible outcomes checked
- [x] No hardcoded secrets in config.py
- [x] `.env` file not committed to git
- [x] Update roadmap.md status: spec-written -> done (when ready)
