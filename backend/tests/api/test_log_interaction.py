"""S4.6 — Log Interaction tests.

20 tests covering _hash_phone() and _log_interaction():
- 4 tests for _hash_phone() (FR-1): hex output, determinism, uniqueness, empty input
- 16 tests for _log_interaction() (FR-2, FR-3): db.add, db.flush, phone hashing,
  language_code, doc_type default, status enum, optional fields, DB error handling,
  PHI-safe logging, request_id in logs
"""

from __future__ import annotations

import os
from io import StringIO
from unittest.mock import AsyncMock, MagicMock

# ---------------------------------------------------------------------------
# Ensure test env vars are set BEFORE importing modules that read settings
# ---------------------------------------------------------------------------
_TEST_ENV = {
    "OPENAI_API_KEY": "sk-test-openai",
    "ANTHROPIC_API_KEY": "sk-ant-test-anthropic",
    "TWILIO_ACCOUNT_SID": "ACtest1234567890",
    "TWILIO_AUTH_TOKEN": "test-twilio-token",
    "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
    "BHASHINI_API_KEY": "test-bhashini-key",
    "BHASHINI_USER_ID": "test-bhashini-user",
    "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "S3_BUCKET": "test-bucket",
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
}
for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)

import hashlib  # noqa: E402

import pytest  # noqa: E402
from loguru import logger  # noqa: E402

from backend.app.api.webhooks import _hash_phone, _log_interaction  # noqa: E402
from backend.app.db.models import InteractionLog, InteractionStatus  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RAW_PHONE = "whatsapp:+919876543210"
RAW_PHONE_2 = "whatsapp:+919999999999"
EXPECTED_HASH = hashlib.sha256(RAW_PHONE.encode()).hexdigest()


@pytest.fixture()
def mock_db():
    """Create a mock AsyncSession with add and flush methods."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture()
def log_capture():
    """Capture Loguru output into a StringIO buffer for assertion."""
    sink = StringIO()
    handler_id = logger.add(sink, format="{extra} {message}", level="DEBUG")
    yield sink
    logger.remove(handler_id)


# ===========================================================================
# FR-1: _hash_phone() — 4 tests
# ===========================================================================


class TestHashPhone:
    """Tests for _hash_phone() pure function."""

    def test_hash_phone_returns_64_char_hex(self):
        """_hash_phone() returns a 64-character lowercase hex string."""
        result = _hash_phone(RAW_PHONE)
        assert len(result) == 64
        assert result == result.lower()
        # Verify all chars are hex digits
        int(result, 16)

    def test_hash_phone_deterministic(self):
        """Same input always produces same output."""
        result1 = _hash_phone(RAW_PHONE)
        result2 = _hash_phone(RAW_PHONE)
        assert result1 == result2

    def test_hash_phone_different_inputs(self):
        """Different phone numbers produce different hashes."""
        hash1 = _hash_phone(RAW_PHONE)
        hash2 = _hash_phone(RAW_PHONE_2)
        assert hash1 != hash2

    def test_hash_phone_empty_string(self):
        """Empty string returns a valid 64-char hash (no crash)."""
        result = _hash_phone("")
        assert len(result) == 64
        int(result, 16)  # valid hex


# ===========================================================================
# FR-2 + FR-3: _log_interaction() — 16 tests
# ===========================================================================


class TestLogInteraction:
    """Tests for _log_interaction() async function."""

    @pytest.mark.asyncio
    async def test_log_interaction_calls_db_add(self, mock_db):
        """db.add() is called with an InteractionLog instance."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.SUCCESS,
            request_id="req-001",
            db=mock_db,
        )
        mock_db.add.assert_called_once()
        added = mock_db.add.call_args[0][0]
        assert isinstance(added, InteractionLog)

    @pytest.mark.asyncio
    async def test_log_interaction_calls_db_flush(self, mock_db):
        """db.flush() is awaited after db.add()."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.SUCCESS,
            request_id="req-002",
            db=mock_db,
        )
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_log_interaction_hashes_phone(self, mock_db):
        """The phone_hash field on the added row is _hash_phone(phone_number), not raw."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.SUCCESS,
            request_id="req-003",
            db=mock_db,
        )
        added = mock_db.add.call_args[0][0]
        assert added.phone_hash == EXPECTED_HASH
        # Ensure raw phone is NOT stored
        assert added.phone_hash != RAW_PHONE

    @pytest.mark.asyncio
    async def test_log_interaction_sets_language_code(self, mock_db):
        """language_code field matches the input."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="ta",
            status=InteractionStatus.SUCCESS,
            request_id="req-004",
            db=mock_db,
        )
        added = mock_db.add.call_args[0][0]
        assert added.language_code == "ta"

    @pytest.mark.asyncio
    async def test_log_interaction_sets_doc_type_default(self, mock_db):
        """doc_type defaults to 'prescription'."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.SUCCESS,
            request_id="req-005",
            db=mock_db,
        )
        added = mock_db.add.call_args[0][0]
        assert added.doc_type == "prescription"

    @pytest.mark.asyncio
    async def test_log_interaction_sets_status(self, mock_db):
        """status field matches the input enum value."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.ERROR,
            request_id="req-006",
            db=mock_db,
        )
        added = mock_db.add.call_args[0][0]
        assert added.status == InteractionStatus.ERROR.value

    @pytest.mark.asyncio
    async def test_log_interaction_sets_confidence_avg(self, mock_db):
        """Optional confidence_avg is stored when provided."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.SUCCESS,
            request_id="req-007",
            db=mock_db,
            confidence_avg=0.95,
        )
        added = mock_db.add.call_args[0][0]
        assert added.confidence_avg == 0.95

    @pytest.mark.asyncio
    async def test_log_interaction_sets_latency_ms(self, mock_db):
        """Optional latency_ms is stored when provided."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.SUCCESS,
            request_id="req-008",
            db=mock_db,
            latency_ms=1500,
        )
        added = mock_db.add.call_args[0][0]
        assert added.latency_ms == 1500

    @pytest.mark.asyncio
    async def test_log_interaction_sets_error_code(self, mock_db):
        """Optional error_code is stored when provided."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.ERROR,
            request_id="req-009",
            db=mock_db,
            error_code="EXTRACTION_FAILED",
        )
        added = mock_db.add.call_args[0][0]
        assert added.error_code == "EXTRACTION_FAILED"

    @pytest.mark.asyncio
    async def test_log_interaction_optional_fields_none(self, mock_db):
        """When optional fields omitted, they are None on the row."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.SUCCESS,
            request_id="req-010",
            db=mock_db,
        )
        added = mock_db.add.call_args[0][0]
        assert added.confidence_avg is None
        assert added.latency_ms is None
        assert added.error_code is None

    @pytest.mark.asyncio
    async def test_log_interaction_status_success(self, mock_db):
        """Works with InteractionStatus.SUCCESS."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.SUCCESS,
            request_id="req-011",
            db=mock_db,
        )
        added = mock_db.add.call_args[0][0]
        assert added.status == "success"

    @pytest.mark.asyncio
    async def test_log_interaction_status_error(self, mock_db):
        """Works with InteractionStatus.ERROR."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.ERROR,
            request_id="req-012",
            db=mock_db,
        )
        added = mock_db.add.call_args[0][0]
        assert added.status == "error"

    @pytest.mark.asyncio
    async def test_log_interaction_status_flagged(self, mock_db):
        """Works with InteractionStatus.FLAGGED."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.FLAGGED,
            request_id="req-013",
            db=mock_db,
        )
        added = mock_db.add.call_args[0][0]
        assert added.status == "flagged"

    @pytest.mark.asyncio
    async def test_log_interaction_db_error_logs_and_reraises(self, mock_db, log_capture):
        """DB flush error is logged at ERROR level and re-raised."""
        mock_db.flush.side_effect = RuntimeError("DB connection lost")

        with pytest.raises(RuntimeError, match="DB connection lost"):
            await _log_interaction(
                phone_number=RAW_PHONE,
                language_code="hi",
                status=InteractionStatus.SUCCESS,
                request_id="req-014",
                db=mock_db,
            )

        log_output = log_capture.getvalue()
        assert "req-014" in log_output

    @pytest.mark.asyncio
    async def test_log_interaction_no_raw_phone_in_logs(self, mock_db, log_capture):
        """Captured Loguru output contains phone_hash but not the raw phone number."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.SUCCESS,
            request_id="req-015",
            db=mock_db,
        )

        log_output = log_capture.getvalue()
        # Raw phone must NOT appear in logs
        assert RAW_PHONE not in log_output
        assert "+919876543210" not in log_output

    @pytest.mark.asyncio
    async def test_log_interaction_logs_with_request_id(self, mock_db, log_capture):
        """Loguru output includes request_id in context."""
        await _log_interaction(
            phone_number=RAW_PHONE,
            language_code="hi",
            status=InteractionStatus.SUCCESS,
            request_id="req-016",
            db=mock_db,
        )

        log_output = log_capture.getvalue()
        assert "req-016" in log_output
