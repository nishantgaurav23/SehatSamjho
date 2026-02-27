"""Tests for app/db/models.py

Tests:
    - Table name and column existence
    - Primary key, unique, and nullable constraints
    - Live DB insert + query round-trip
    - server_default sets created_at automatically
    - Duplicate request_id raises IntegrityError
    - error_code is nullable

Requires PostgreSQL + migration: `make services && make local-migrate`
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TranslationLog


# ── Static structure tests (no DB needed) ─────────────────────────────────────

def test_table_name():
    assert TranslationLog.__tablename__ == "translation_logs"


def test_all_columns_exist():
    cols = {c.key for c in inspect(TranslationLog).columns}
    expected = {
        "id", "created_at", "request_id", "phone_hash",
        "language_code", "doc_type", "latency_ms",
        "drug_count", "has_audio", "status", "error_code",
    }
    assert expected.issubset(cols)


def test_primary_key_is_id():
    pks = [c.key for c in inspect(TranslationLog).columns if c.primary_key]
    assert pks == ["id"]


def test_request_id_is_unique():
    col = next(c for c in inspect(TranslationLog).columns if c.key == "request_id")
    assert col.unique is True


def test_nullable_constraints():
    cols = {c.key: c for c in inspect(TranslationLog).columns}
    for required in [
        "request_id", "phone_hash", "language_code",
        "doc_type", "latency_ms", "drug_count", "has_audio", "status",
    ]:
        assert cols[required].nullable is False, f"{required} must be NOT NULL"
    assert cols["error_code"].nullable is True


# ── Live DB tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_insert_and_query(db_session: AsyncSession):
    """Row can be written and read back within the same transaction."""
    row = TranslationLog(
        request_id="SM_model_001",
        phone_hash="a" * 64,
        language_code="hi",
        doc_type="prescription",
        latency_ms=1200,
        drug_count=3,
        has_audio=False,
        status="success",
    )
    db_session.add(row)
    await db_session.flush()

    result = await db_session.execute(
        text(
            "SELECT request_id, language_code, drug_count "
            "FROM translation_logs WHERE request_id = 'SM_model_001'"
        )
    )
    fetched = result.fetchone()
    assert fetched is not None
    assert fetched.request_id    == "SM_model_001"
    assert fetched.language_code == "hi"
    assert fetched.drug_count    == 3


@pytest.mark.asyncio
async def test_created_at_set_by_db(db_session: AsyncSession):
    """created_at is populated by server_default — app code sets nothing."""
    row = TranslationLog(
        request_id="SM_model_002",
        phone_hash="b" * 64,
        language_code="ta",
        doc_type="lab_report",
        latency_ms=800,
    )
    db_session.add(row)
    await db_session.flush()
    await db_session.refresh(row)
    assert row.created_at is not None


@pytest.mark.asyncio
async def test_error_code_nullable(db_session: AsyncSession):
    """error_code defaults to NULL when omitted."""
    row = TranslationLog(
        request_id="SM_model_003",
        phone_hash="c" * 64,
        language_code="bn",
        doc_type="unknown",
        latency_ms=500,
    )
    db_session.add(row)
    await db_session.flush()
    await db_session.refresh(row)
    assert row.error_code is None


@pytest.mark.asyncio
async def test_unique_request_id_enforced(db_session: AsyncSession):
    """Two rows with the same request_id must raise IntegrityError."""
    row1 = TranslationLog(
        request_id="SM_dup",
        phone_hash="d" * 64,
        language_code="hi",
        doc_type="prescription",
        latency_ms=100,
    )
    row2 = TranslationLog(
        request_id="SM_dup",
        phone_hash="e" * 64,
        language_code="en",
        doc_type="prescription",
        latency_ms=200,
    )
    db_session.add(row1)
    await db_session.flush()

    db_session.add(row2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
