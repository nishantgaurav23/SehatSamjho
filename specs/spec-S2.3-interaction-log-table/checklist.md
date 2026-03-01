# Checklist — Spec S2.3: Interaction Log Table

## Phase 1: Setup & Dependencies
- [x] Verify S2.1 (Async SQLAlchemy engine) is implemented and passing
- [x] Confirm `Base` is importable from `backend.app.db.database`
- [x] Create target file: `backend/app/db/models.py`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/db/test_models.py`
- [x] Write test: `test_import_interaction_log`
- [x] Write test: `test_import_interaction_status`
- [x] Write test: `test_tablename`
- [x] Write test: `test_column_names_exact`
- [x] Write test: `test_id_column_uuid_primary_key`
- [x] Write test: `test_id_column_has_default`
- [x] Write test: `test_created_at_timezone_aware`
- [x] Write test: `test_created_at_server_default`
- [x] Write test: `test_phone_hash_string_64`
- [x] Write test: `test_language_code_non_nullable`
- [x] Write test: `test_doc_type_default`
- [x] Write test: `test_confidence_avg_nullable`
- [x] Write test: `test_latency_ms_nullable`
- [x] Write test: `test_status_default_success`
- [x] Write test: `test_error_code_nullable`
- [x] Write test: `test_no_phi_columns`
- [x] Write test: `test_interaction_status_enum_members`
- [x] Write test: `test_interaction_status_values`
- [x] Write test: `test_repr`
- [x] Write test: `test_registered_in_base_metadata`
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement `InteractionStatus` enum in `backend/app/db/models.py`
- [x] Implement `InteractionLog` ORM model with all 9 columns
- [x] Add `__repr__` method
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify `InteractionLog` registers in `Base.metadata.tables`
- [x] No router wiring needed (model only)
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 11 tangible outcomes checked
- [x] No hardcoded secrets
- [x] No PHI columns present
- [x] Zero-PHI test passes
- [x] Update roadmap.md status: spec-written -> done
