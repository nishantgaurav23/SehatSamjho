"""S2.3 — Tests for InteractionLog ORM model and InteractionStatus enum.

Pure model introspection — no database connection needed.
"""

import uuid

from sqlalchemy import UUID, DateTime, Float, Integer, String

from backend.app.db.database import Base
from backend.app.db.models import InteractionLog, InteractionStatus


# ── Test Imports ────────────────────────────────────────────────────────────────


class TestImports:
    """Verify that InteractionLog and InteractionStatus are importable."""

    def test_import_interaction_log(self):
        assert InteractionLog is not None

    def test_import_interaction_status(self):
        assert InteractionStatus is not None


# ── Test InteractionStatus Enum ─────────────────────────────────────────────────


class TestInteractionStatusEnum:
    """FR-1: InteractionStatus enum with exactly 3 members."""

    def test_interaction_status_enum_members(self):
        members = set(InteractionStatus.__members__.keys())
        assert members == {"SUCCESS", "ERROR", "FLAGGED"}

    def test_interaction_status_values(self):
        assert InteractionStatus.SUCCESS.value == "success"
        assert InteractionStatus.ERROR.value == "error"
        assert InteractionStatus.FLAGGED.value == "flagged"


# ── Test InteractionLog ORM Model ───────────────────────────────────────────────


class TestTableName:
    """FR-2: Table name is 'interaction_log'."""

    def test_tablename(self):
        assert InteractionLog.__tablename__ == "interaction_log"


class TestColumns:
    """FR-2: Exactly 9 columns with correct types and constraints."""

    ALLOWED_COLUMNS = {
        "id",
        "created_at",
        "phone_hash",
        "language_code",
        "doc_type",
        "confidence_avg",
        "latency_ms",
        "status",
        "error_code",
    }

    def _col(self, name: str):
        return InteractionLog.__table__.columns[name]

    def test_column_names_exact(self):
        actual = set(c.name for c in InteractionLog.__table__.columns)
        assert actual == self.ALLOWED_COLUMNS

    # ── id ──
    def test_id_column_uuid_primary_key(self):
        col = self._col("id")
        assert isinstance(col.type, UUID)
        assert col.primary_key is True

    def test_id_column_has_default(self):
        col = self._col("id")
        assert col.default is not None

    # ── created_at ──
    def test_created_at_timezone_aware(self):
        col = self._col("created_at")
        assert isinstance(col.type, DateTime)
        assert col.type.timezone is True

    def test_created_at_server_default(self):
        col = self._col("created_at")
        assert col.server_default is not None

    # ── phone_hash ──
    def test_phone_hash_string_64(self):
        col = self._col("phone_hash")
        assert isinstance(col.type, String)
        assert col.type.length == 64
        assert col.nullable is False

    # ── language_code ──
    def test_language_code_non_nullable(self):
        col = self._col("language_code")
        assert isinstance(col.type, String)
        assert col.type.length == 10
        assert col.nullable is False

    # ── doc_type ──
    def test_doc_type_default(self):
        col = self._col("doc_type")
        assert isinstance(col.type, String)
        assert col.type.length == 50
        assert col.nullable is False
        assert col.default is not None
        assert col.default.arg == "prescription"

    # ── confidence_avg ──
    def test_confidence_avg_nullable(self):
        col = self._col("confidence_avg")
        assert isinstance(col.type, Float)
        assert col.nullable is True

    # ── latency_ms ──
    def test_latency_ms_nullable(self):
        col = self._col("latency_ms")
        assert isinstance(col.type, Integer)
        assert col.nullable is True

    # ── status ──
    def test_status_default_success(self):
        col = self._col("status")
        assert isinstance(col.type, String)
        assert col.type.length == 20
        assert col.nullable is False
        assert col.default is not None
        assert col.default.arg == "success"

    # ── error_code ──
    def test_error_code_nullable(self):
        col = self._col("error_code")
        assert isinstance(col.type, String)
        assert col.type.length == 100
        assert col.nullable is True


# ── Test PHI Enforcement ────────────────────────────────────────────────────────


class TestZeroPHI:
    """FR-3: No columns that could store PHI."""

    PHI_COLUMN_NAMES = {
        "phone",
        "phone_number",
        "patient_name",
        "image",
        "image_data",
        "extracted_text",
        "translated_text",
        "prescription_text",
    }

    def test_no_phi_columns(self):
        actual = set(c.name for c in InteractionLog.__table__.columns)
        phi_found = actual & self.PHI_COLUMN_NAMES
        assert phi_found == set(), f"PHI columns found: {phi_found}"


# ── Test __repr__ ───────────────────────────────────────────────────────────────


class TestRepr:
    """FR-4: Human-readable repr."""

    def test_repr(self):
        test_id = uuid.uuid4()
        log = InteractionLog(
            id=test_id,
            phone_hash="a" * 64,
            language_code="hi",
            status="success",
        )
        expected = f"<InteractionLog id={test_id} status=success lang=hi>"
        assert repr(log) == expected


# ── Test Base.metadata Registration ─────────────────────────────────────────────


class TestMetadataRegistration:
    """FR-5: InteractionLog is registered in Base.metadata.tables."""

    def test_registered_in_base_metadata(self):
        assert "interaction_log" in Base.metadata.tables
