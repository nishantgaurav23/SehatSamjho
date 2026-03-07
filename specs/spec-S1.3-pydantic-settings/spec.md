# Spec S1.3 — pydantic-settings config

## Overview
Centralised application settings loaded from environment variables via `pydantic-settings`.
All secrets (API keys, database credentials, service URLs) are declared as typed fields on a
single `Settings` class, populated from `.env` at import time. No hardcoded keys anywhere in
the codebase — every secret flows through `config.py`.

## Dependencies
- **S1.1** (Dependency declaration) — `pydantic-settings` must be declared in `pyproject.toml`.

## Target Location
- `backend/app/core/config.py`

---

## Functional Requirements

### FR-1: Settings class with all required fields
- **What**: A `Settings` class (subclassing `pydantic_settings.BaseSettings`) declaring every
  environment variable the application needs.
- **Fields** (secrets are required with no defaults; AWS keys default to empty string for EC2 IAM role support):

  | Field | Type | Default | Source |
  |-------|------|---------|--------|
  | `OPENAI_API_KEY` | `str` | — | `.env` |
  | `ANTHROPIC_API_KEY` | `str` | — | `.env` |
  | `TWILIO_ACCOUNT_SID` | `str` | — | `.env` |
  | `TWILIO_AUTH_TOKEN` | `str` | — | `.env` |
  | `TWILIO_WHATSAPP_FROM` | `str` | — | `.env` |
  | `BHASHINI_API_KEY` | `str` | — | `.env` |
  | `BHASHINI_USER_ID` | `str` | — | `.env` |
  | `AWS_ACCESS_KEY_ID` | `str` | `""` (empty) | `.env` |
  | `AWS_SECRET_ACCESS_KEY` | `str` | `""` (empty) | `.env` |
  | `S3_BUCKET` | `str` | `"sehatsamjho-audio"` | `.env` |
  | `DATABASE_URL` | `str` | `"postgresql+asyncpg://postgres:postgres@localhost:5432/sehatsamjho"` | `.env` |
  | `REDIS_URL` | `str` | `"redis://localhost:6379/0"` | `.env` |

- **Outputs**: A validated `Settings` instance.
- **Edge cases**: Missing required field → `pydantic` `ValidationError` at startup (fail fast). AWS keys are optional — on EC2, the IAM instance profile provides S3 credentials automatically.

### FR-2: Module-level singleton `settings`
- **What**: A module-level `settings = Settings()` instance so any module can
  `from backend.app.core.config import settings`.
- **Inputs**: Environment variables (or `.env` file).
- **Outputs**: A single shared `Settings` object.
- **Edge cases**: Importing `config` without the required env vars set raises `ValidationError`.

### FR-3: `.env` file loading via `model_config`
- **What**: The `Settings` class must declare `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")` so that `pydantic-settings` auto-loads variables from the project root `.env` file.
- **Edge cases**: If `.env` does not exist, settings fall back to real environment variables (no crash).

### FR-4: Case-insensitive env var matching
- **What**: Environment variable names are matched case-insensitively (default `pydantic-settings` behaviour). E.g., `openai_api_key` and `OPENAI_API_KEY` both resolve.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `from backend.app.core.config import settings` succeeds when all 12 env vars are set.
- [ ] **Outcome 2**: `settings.OPENAI_API_KEY` returns the value from the environment / `.env` file.
- [ ] **Outcome 3**: Omitting a required field (e.g., `OPENAI_API_KEY`) raises `ValidationError`.
- [ ] **Outcome 4**: `S3_BUCKET` defaults to `"sehatsamjho-audio"` when not set.
- [ ] **Outcome 5**: `DATABASE_URL` defaults to the local asyncpg connection string when not set.
- [ ] **Outcome 6**: `REDIS_URL` defaults to `"redis://localhost:6379/0"` when not set.
- [ ] **Outcome 7**: `settings` is a module-level singleton (same object on repeated imports).
- [ ] **Outcome 8**: The `Settings` class inherits from `pydantic_settings.BaseSettings`.

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

1. **test_settings_class_exists**: `Settings` is importable from `backend.app.core.config`.
2. **test_settings_inherits_base_settings**: `Settings` is a subclass of `pydantic_settings.BaseSettings`.
3. **test_settings_has_all_fields**: All 12 fields exist on the `Settings` class with correct types.
4. **test_settings_loads_from_env**: Setting env vars produces a valid `Settings()` instance.
5. **test_settings_required_fields_missing**: Omitting a required field raises `ValidationError`.
6. **test_settings_s3_bucket_default**: `S3_BUCKET` defaults to `"sehatsamjho-audio"`.
7. **test_settings_database_url_default**: `DATABASE_URL` defaults to the local asyncpg string.
8. **test_settings_redis_url_default**: `REDIS_URL` defaults to `"redis://localhost:6379/0"`.
9. **test_settings_singleton_exported**: `settings` is a module-level attribute of `backend.app.core.config`.
10. **test_settings_env_file_configured**: `model_config` includes `env_file=".env"`.

### Mocking Strategy
- Use `monkeypatch.setenv` / `monkeypatch.delenv` to control environment variables per test.
- No external services involved — purely static validation tests.

### Coverage Expectation
- 100% of `config.py` lines covered (the file is small and declarative).

---

## References
- `roadmap.md` — S1.3 row
- `.env.example` — canonical list of 12 env vars
- `pydantic-settings` docs: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
