# Spec S2.5 — Alembic Migrations Setup

## Overview
Configure Alembic for async SQLAlchemy migration management. This includes `alembic.ini` (with correct script location and sys_path), an async-aware `env.py` that imports the project's `Base` and `engine`, the standard `script.py.mako` template, and an initial auto-generated migration that creates the `interaction_log` table defined in S2.3.

## Dependencies
- **S2.1** (Async SQLAlchemy engine) — provides `engine`, `Base` from `backend/app/db/database.py`
- **S2.3** (Interaction log table) — provides `InteractionLog` model imported via `backend/app/db/models.py`

## Target Location
- `backend/alembic.ini` — Alembic configuration file
- `backend/alembic/` — migrations directory
  - `env.py` — async migration environment
  - `script.py.mako` — migration template
  - `versions/` — migration files

---

## Functional Requirements

### FR-1: alembic.ini Configuration
- **What**: A valid `alembic.ini` at `backend/alembic.ini` that Alembic CLI can locate and parse.
- **Inputs**: None (static config file).
- **Outputs**: Configuration with:
  - `script_location = alembic` (relative to backend/)
  - `prepend_sys_path = ..` (so `backend.app.*` imports resolve from project root)
  - `sqlalchemy.url` left empty or as placeholder — the real URL is injected from `settings.DATABASE_URL` in `env.py` at runtime.
- **Edge cases**: Must not hardcode any real database URL or secret.

### FR-2: Async env.py
- **What**: `backend/alembic/env.py` that runs migrations using the project's async engine.
- **Inputs**: `Base.metadata` (target_metadata), `settings.DATABASE_URL` (connection string).
- **Outputs**: Properly configured Alembic environment supporting:
  - `run_migrations_offline()` — generates SQL without a live connection (uses `settings.DATABASE_URL`).
  - `run_migrations_online()` — uses `create_async_engine` with `settings.DATABASE_URL`, runs migrations inside `connection.run_sync()`.
- **Edge cases**: Must import all model modules (at minimum `backend.app.db.models`) so that `Base.metadata` includes all table definitions for autogenerate.

### FR-3: script.py.mako Template
- **What**: Standard Alembic Mako template for generating migration files.
- **Inputs**: None (static template).
- **Outputs**: Template producing migration files with `revision`, `down_revision`, `upgrade()`, and `downgrade()` functions.

### FR-4: Initial Migration — interaction_log Table
- **What**: A migration file in `backend/alembic/versions/` that creates the `interaction_log` table.
- **Inputs**: Auto-generated from `Base.metadata` diff against an empty database.
- **Outputs**: Migration with:
  - `upgrade()`: Creates `interaction_log` table with columns: id (UUID PK), created_at (DateTime TZ), phone_hash (String 64), language_code (String 10), doc_type (String 50), confidence_avg (Float nullable), latency_ms (Integer nullable), status (String 20), error_code (String 100 nullable).
  - `downgrade()`: Drops `interaction_log` table.
- **Edge cases**: Column types and constraints must exactly match `InteractionLog` model in `backend/app/db/models.py`.

### FR-5: Alembic Dependency in pyproject.toml
- **What**: `alembic>=1.12` must be present in the project's runtime dependencies.
- **Inputs**: `pyproject.toml` dependencies list.
- **Outputs**: Alembic is importable after `uv pip install -r pyproject.toml`.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `alembic.ini` exists at `backend/alembic.ini` with correct `script_location` and `prepend_sys_path`
- [ ] **Outcome 2**: `backend/alembic/env.py` exists, imports `Base` from `backend.app.db.database`, imports `backend.app.db.models`, uses async engine with `settings.DATABASE_URL`
- [ ] **Outcome 3**: `backend/alembic/script.py.mako` exists as a valid Mako template
- [ ] **Outcome 4**: At least one migration file exists in `backend/alembic/versions/` that creates the `interaction_log` table
- [ ] **Outcome 5**: `downgrade()` in the initial migration drops the `interaction_log` table
- [ ] **Outcome 6**: `alembic>=1.12` is listed in `pyproject.toml` dependencies
- [ ] **Outcome 7**: `make local-migrate` (runs `cd backend && alembic upgrade head`) can parse the config without import errors (tested via dry-run / config validation)

---

## Test-Driven Requirements

### Tests to Write First (Red → Green)
1. **test_alembic_ini_exists**: Verify `backend/alembic.ini` exists on disk.
2. **test_alembic_ini_script_location**: Parse INI and assert `script_location = alembic`.
3. **test_alembic_ini_prepend_sys_path**: Parse INI and assert `prepend_sys_path` includes `..`.
4. **test_alembic_ini_no_hardcoded_url**: Assert `sqlalchemy.url` is empty or a placeholder (not a real connection string).
5. **test_env_py_exists**: Verify `backend/alembic/env.py` exists.
6. **test_env_py_imports_base**: Read `env.py` source and assert it imports `Base` from `backend.app.db.database`.
7. **test_env_py_imports_models**: Read `env.py` source and assert it imports `backend.app.db.models` (so autogenerate sees all tables).
8. **test_env_py_uses_async_engine**: Read `env.py` source and assert it references `create_async_engine` or `async_engine_from_config`.
9. **test_env_py_uses_settings_database_url**: Read `env.py` source and assert it reads `settings.DATABASE_URL`.
10. **test_script_mako_exists**: Verify `backend/alembic/script.py.mako` exists.
11. **test_script_mako_has_revision**: Read template and assert it contains `revision` and `down_revision` variables.
12. **test_versions_dir_exists**: Verify `backend/alembic/versions/` directory exists.
13. **test_initial_migration_exists**: At least one `.py` file exists in `backend/alembic/versions/`.
14. **test_initial_migration_has_upgrade**: Read the migration file and assert it defines an `upgrade()` function.
15. **test_initial_migration_has_downgrade**: Read the migration file and assert it defines a `downgrade()` function.
16. **test_initial_migration_creates_interaction_log**: Read the migration `upgrade()` and assert it contains `create_table` with `interaction_log`.
17. **test_initial_migration_downgrade_drops_table**: Read the migration `downgrade()` and assert it contains `drop_table` with `interaction_log`.
18. **test_alembic_dependency_in_pyproject**: Parse `pyproject.toml` and assert `alembic>=1.12` is in dependencies.
19. **test_alembic_config_loadable**: Import `alembic.config.Config`, load `backend/alembic.ini`, assert no errors.
20. **test_interaction_log_columns_in_migration**: Read migration and verify all 9 column names (id, created_at, phone_hash, language_code, doc_type, confidence_avg, latency_ms, status, error_code) appear.

### Mocking Strategy
- No external services needed — all tests are static file/config validation.
- `test_alembic_config_loadable` uses Alembic's own config parser, no DB connection needed.

### Coverage Expectation
- 20 tests covering all FRs. All are static/file-based — fast, no mocking required.

---

## References
- roadmap.md: S2.5 spec definition
- `backend/app/db/database.py`: `engine`, `Base`, `settings.DATABASE_URL` (S2.1)
- `backend/app/db/models.py`: `InteractionLog`, `InteractionStatus` (S2.3)
- `backend/app/core/config.py`: `settings.DATABASE_URL` (S1.3)
- Alembic async documentation: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic
