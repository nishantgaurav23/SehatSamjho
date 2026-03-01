# Spec S2.3 — Interaction Log Table

## Overview
Defines the `interaction_log` PostgreSQL table via SQLAlchemy ORM in `backend/app/db/models.py`. This table stores metadata about every completed prescription-translation pipeline run. **Zero PHI**: raw phone numbers are SHA-256 hashed, and no image content or extracted text is ever persisted. The table is the sole source of analytics data for the B2B dashboard.

## Dependencies
- **S2.1** (Async SQLAlchemy engine) — provides `Base`, `engine`, `AsyncSessionLocal`

## Target Location
- `backend/app/db/models.py`

---

## Functional Requirements

### FR-1: InteractionStatus Enum
- **What**: A Python `enum.Enum` subclass representing the status of a pipeline interaction.
- **Values**: `SUCCESS = "success"`, `ERROR = "error"`, `FLAGGED = "flagged"`
- **Storage**: Mapped to a PostgreSQL `VARCHAR` column (using SQLAlchemy `Enum` with `values_callable` or string-based storage to avoid DDL enum creation issues).

### FR-2: InteractionLog ORM Model
- **What**: A SQLAlchemy ORM model mapped to the `interaction_log` table.
- **Table name**: `interaction_log`
- **Inherits from**: `Base` (from `backend.app.db.database`)
- **Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `UUID` | PK, default `uuid4` | Unique interaction identifier |
| `created_at` | `DateTime(timezone=True)` | NOT NULL, default `func.now()` | Timestamp of log entry creation |
| `phone_hash` | `String(64)` | NOT NULL | SHA-256 hex digest of phone number (no raw phone ever stored) |
| `language_code` | `String(10)` | NOT NULL | ISO 639-1 code (e.g., "hi", "ta", "te") |
| `doc_type` | `String(50)` | NOT NULL, default `"prescription"` | Document type (prescription, lab_report, etc.) |
| `confidence_avg` | `Float` | Nullable | Average confidence score across extracted fields (0.0–1.0) |
| `latency_ms` | `Integer` | Nullable | End-to-end pipeline latency in milliseconds |
| `status` | `String(20)` | NOT NULL, default `"success"` | One of: success, error, flagged |
| `error_code` | `String(100)` | Nullable | Machine-readable error code (e.g., "NOT_MEDICAL_DOC", "IMAGE_UNREADABLE") |

### FR-3: Zero-PHI Enforcement
- **What**: The model must NOT contain any column that stores raw phone numbers, patient names, image bytes, extracted prescription text, or translated text.
- **Validation**: Code review + test assertions that the model's column names are exactly the allowed set.

### FR-4: `__repr__` Method
- **What**: Human-readable string representation for debugging.
- **Format**: `<InteractionLog id={id} status={status} lang={language_code}>`

### FR-5: Table Metadata Accessibility
- **What**: Importing `InteractionLog` must register it with `Base.metadata` so that Alembic (S2.5) can auto-generate migrations.
- **Verification**: `Base.metadata.tables` contains `"interaction_log"` after import.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `from backend.app.db.models import InteractionLog` succeeds without error
- [ ] **Outcome 2**: `InteractionLog.__tablename__` equals `"interaction_log"`
- [ ] **Outcome 3**: The model has exactly these columns: `id`, `created_at`, `phone_hash`, `language_code`, `doc_type`, `confidence_avg`, `latency_ms`, `status`, `error_code`
- [ ] **Outcome 4**: `id` column is UUID type with a default (uuid4)
- [ ] **Outcome 5**: `created_at` has server default via `func.now()` and is timezone-aware
- [ ] **Outcome 6**: `phone_hash` is String(64), non-nullable (SHA-256 hex length)
- [ ] **Outcome 7**: `status` default is `"success"` and only allows valid InteractionStatus values
- [ ] **Outcome 8**: No PHI columns exist — column names are exactly the allowed set
- [ ] **Outcome 9**: `InteractionLog` is registered in `Base.metadata.tables`
- [ ] **Outcome 10**: `repr()` returns expected format string
- [ ] **Outcome 11**: `InteractionStatus` enum has exactly 3 members: SUCCESS, ERROR, FLAGGED

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

1. **test_import_interaction_log**: Import `InteractionLog` from `backend.app.db.models` succeeds
2. **test_import_interaction_status**: Import `InteractionStatus` from `backend.app.db.models` succeeds
3. **test_tablename**: `InteractionLog.__tablename__ == "interaction_log"`
4. **test_column_names_exact**: Column names are exactly the 9 allowed columns (no more, no less)
5. **test_id_column_uuid_primary_key**: `id` column is UUID type and is primary key
6. **test_id_column_has_default**: `id` column has a default (uuid4 callable)
7. **test_created_at_timezone_aware**: `created_at` column uses `DateTime(timezone=True)`
8. **test_created_at_server_default**: `created_at` has a server_default set
9. **test_phone_hash_string_64**: `phone_hash` is String(64) and non-nullable
10. **test_language_code_non_nullable**: `language_code` is String(10) and non-nullable
11. **test_doc_type_default**: `doc_type` default is `"prescription"`
12. **test_confidence_avg_nullable**: `confidence_avg` is Float and nullable
13. **test_latency_ms_nullable**: `latency_ms` is Integer and nullable
14. **test_status_default_success**: `status` default is `"success"`
15. **test_error_code_nullable**: `error_code` is String(100) and nullable
16. **test_no_phi_columns**: Column names do NOT include any of: phone, phone_number, patient_name, image, image_data, extracted_text, translated_text, prescription_text
17. **test_interaction_status_enum_members**: `InteractionStatus` has exactly SUCCESS, ERROR, FLAGGED
18. **test_interaction_status_values**: Values are "success", "error", "flagged"
19. **test_repr**: `repr(InteractionLog(...))` matches expected format
20. **test_registered_in_base_metadata**: `"interaction_log"` in `Base.metadata.tables`

### Mocking Strategy
- No external services needed — this is pure ORM model definition
- Tests inspect SQLAlchemy column metadata (type, nullable, default) without connecting to a real database
- Use `inspect(InteractionLog)` or `InteractionLog.__table__.columns` for introspection

### Coverage Expectation
- 100% of columns verified for type, nullable, and default
- PHI enforcement explicitly tested
- Enum members and values explicitly tested

---

## References
- roadmap.md: Phase 2, S2.3
- design.md, requirements.md
- S2.1 spec (provides `Base`)
