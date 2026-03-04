"""S8.3 — Tests for lookup_drug().

20 tests covering: _normalize_drug_name, DRUG_CACHE_TTL_SECONDS,
_call_indianmedicinedb stub, lookup_drug (Redis hit/miss, API fallback,
caching, error resilience, logging, normalization).
"""

import asyncio
import inspect
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.models.schemas import DrugInfo


# ── Sample fixtures ──────────────────────────────────────────────────────────

SAMPLE_DRUG = DrugInfo(
    brand_name="Amoxicillin",
    generic_name="amoxicillin",
    therapeutic_class="Antibiotic",
    purpose_en="Treats bacterial infections",
    side_effects_en="Nausea, rash",
    timing_instructions="After meals",
    known_interactions="Warfarin",
)

SAMPLE_DRUG_JSON = SAMPLE_DRUG.model_dump_json()


# ══════════════════════════════════════════════════════════════════════════════
# _normalize_drug_name
# ══════════════════════════════════════════════════════════════════════════════


class TestNormalizeDrugName:
    """FR-1: Pure function — lowercase, strip, whitespace-collapse."""

    def test_normalize_drug_name_basic(self):
        from backend.app.services.drug_lookup import _normalize_drug_name

        assert _normalize_drug_name("Amoxicillin") == "amoxicillin"
        assert _normalize_drug_name("  Paracetamol  ") == "paracetamol"

    def test_normalize_drug_name_whitespace_collapse(self):
        from backend.app.services.drug_lookup import _normalize_drug_name

        assert _normalize_drug_name("  Paracetamol  500mg  ") == "paracetamol 500mg"
        assert _normalize_drug_name("A   B   C") == "a b c"

    def test_normalize_drug_name_empty(self):
        from backend.app.services.drug_lookup import _normalize_drug_name

        assert _normalize_drug_name("") == ""
        assert _normalize_drug_name("   ") == ""


# ══════════════════════════════════════════════════════════════════════════════
# DRUG_CACHE_TTL_SECONDS constant
# ══════════════════════════════════════════════════════════════════════════════


class TestDrugCacheTTL:
    """FR-4: Module-level constant = 604800 (7 days)."""

    def test_drug_cache_ttl_constant(self):
        from backend.app.services.drug_lookup import DRUG_CACHE_TTL_SECONDS

        assert DRUG_CACHE_TTL_SECONDS == 604800


# ══════════════════════════════════════════════════════════════════════════════
# _call_indianmedicinedb stub
# ══════════════════════════════════════════════════════════════════════════════


class TestCallIndianMedicineDBStub:
    """FR-5: Async stub that always returns None."""

    def test_call_indianmedicinedb_stub(self):
        from backend.app.services.drug_lookup import _call_indianmedicinedb

        assert asyncio.iscoroutinefunction(_call_indianmedicinedb)
        result = asyncio.get_event_loop().run_until_complete(_call_indianmedicinedb("Amoxicillin"))
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# lookup_drug — import / signature
# ══════════════════════════════════════════════════════════════════════════════


class TestLookupDrugBasic:
    """FR-2: Importability and async signature."""

    def test_lookup_drug_importable(self):
        from backend.app.services.drug_lookup import lookup_drug  # noqa: F401

    def test_lookup_drug_is_async(self):
        from backend.app.services.drug_lookup import lookup_drug

        assert asyncio.iscoroutinefunction(lookup_drug)

    def test_lookup_drug_signature(self):
        from backend.app.services.drug_lookup import lookup_drug

        sig = inspect.signature(lookup_drug)
        params = list(sig.parameters.keys())
        assert "redis_client" in params
        assert "medicine_name" in params
        assert "request_id" in params
        # request_id should be optional
        assert sig.parameters["request_id"].default is None


# ══════════════════════════════════════════════════════════════════════════════
# lookup_drug — Redis hit path
# ══════════════════════════════════════════════════════════════════════════════


class TestLookupDrugRedisHit:
    """FR-2: Redis GET returns valid JSON → returns DrugInfo."""

    @pytest.mark.asyncio
    async def test_lookup_drug_redis_hit(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=SAMPLE_DRUG_JSON)

        result = await lookup_drug(mock_redis, "Amoxicillin", request_id="req-1")

        assert result is not None
        assert isinstance(result, DrugInfo)
        assert result.brand_name == "Amoxicillin"
        mock_redis.get.assert_called_once_with("drug:amoxicillin")


# ══════════════════════════════════════════════════════════════════════════════
# lookup_drug — Redis miss, API miss
# ══════════════════════════════════════════════════════════════════════════════


class TestLookupDrugRedisMissAPIMiss:
    """FR-3: Redis miss + API stub returns None → returns None."""

    @pytest.mark.asyncio
    async def test_lookup_drug_redis_miss_api_miss(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        result = await lookup_drug(mock_redis, "UnknownDrug")

        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# lookup_drug — Redis miss, API hit (+ caching)
# ══════════════════════════════════════════════════════════════════════════════


class TestLookupDrugRedisMissAPIHit:
    """FR-3: Redis miss + mocked API returns DrugInfo → cache + return."""

    @pytest.mark.asyncio
    async def test_lookup_drug_redis_miss_api_hit(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        with patch(
            "backend.app.services.drug_lookup._call_indianmedicinedb",
            return_value=SAMPLE_DRUG,
        ):
            result = await lookup_drug(mock_redis, "Amoxicillin", request_id="req-2")

        assert result is not None
        assert isinstance(result, DrugInfo)
        assert result.brand_name == "Amoxicillin"
        # Should have cached the result
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_lookup_drug_cache_ttl_on_api_result(self):
        from backend.app.services.drug_lookup import DRUG_CACHE_TTL_SECONDS, lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock()

        with patch(
            "backend.app.services.drug_lookup._call_indianmedicinedb",
            return_value=SAMPLE_DRUG,
        ):
            await lookup_drug(mock_redis, "Amoxicillin")

        # Verify TTL is set to 7 days
        call_args = mock_redis.set.call_args
        assert call_args is not None
        # Check key
        assert call_args[0][0] == "drug:amoxicillin"
        # Check TTL via ex kwarg
        assert call_args[1].get("ex") == DRUG_CACHE_TTL_SECONDS


# ══════════════════════════════════════════════════════════════════════════════
# lookup_drug — empty name
# ══════════════════════════════════════════════════════════════════════════════


class TestLookupDrugEmptyName:
    """FR-2: Empty name → None immediately (no Redis call)."""

    @pytest.mark.asyncio
    async def test_lookup_drug_empty_name(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock()

        result = await lookup_drug(mock_redis, "")

        assert result is None
        mock_redis.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_lookup_drug_whitespace_only_name(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock()

        result = await lookup_drug(mock_redis, "   ")

        assert result is None
        mock_redis.get.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# lookup_drug — error resilience
# ══════════════════════════════════════════════════════════════════════════════


class TestLookupDrugErrorResilience:
    """FR-2/FR-3: Errors do not propagate — returns None gracefully."""

    @pytest.mark.asyncio
    async def test_lookup_drug_redis_error_resilience(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        result = await lookup_drug(mock_redis, "Amoxicillin")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_drug_api_error_resilience(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch(
            "backend.app.services.drug_lookup._call_indianmedicinedb",
            side_effect=RuntimeError("API exploded"),
        ):
            result = await lookup_drug(mock_redis, "Amoxicillin")

        assert result is None

    @pytest.mark.asyncio
    async def test_lookup_drug_invalid_json_in_redis(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value="NOT VALID JSON {{{{")

        # Should not crash — falls through to API path
        result = await lookup_drug(mock_redis, "Amoxicillin")

        # API stub returns None, so result is None
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# lookup_drug — logging
# ══════════════════════════════════════════════════════════════════════════════


class TestLookupDrugLogging:
    """FR-6: Loguru logging at appropriate levels."""

    @pytest.mark.asyncio
    async def test_lookup_drug_logging_cache_hit(self, capfd):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=SAMPLE_DRUG_JSON)

        with patch("backend.app.services.drug_lookup.logger") as mock_logger:
            await lookup_drug(mock_redis, "Amoxicillin", request_id="req-log-1")

            # Should log cache hit at debug level
            mock_logger.debug.assert_called()
            debug_messages = [str(call) for call in mock_logger.debug.call_args_list]
            assert any("hit" in msg.lower() or "found" in msg.lower() for msg in debug_messages)

    @pytest.mark.asyncio
    async def test_lookup_drug_logging_cache_miss(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("backend.app.services.drug_lookup.logger") as mock_logger:
            await lookup_drug(mock_redis, "UnknownDrug", request_id="req-log-2")

            mock_logger.debug.assert_called()
            debug_messages = [str(call) for call in mock_logger.debug.call_args_list]
            assert any(
                "miss" in msg.lower() or "not found" in msg.lower() for msg in debug_messages
            )


# ══════════════════════════════════════════════════════════════════════════════
# lookup_drug — normalization
# ══════════════════════════════════════════════════════════════════════════════


class TestLookupDrugNormalization:
    """FR-2: Name is normalized before Redis key lookup."""

    @pytest.mark.asyncio
    async def test_lookup_drug_normalizes_name(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=SAMPLE_DRUG_JSON)

        await lookup_drug(mock_redis, "  AMOXICILLIN  ")

        # Should look up the normalized key
        mock_redis.get.assert_called_once_with("drug:amoxicillin")


# ══════════════════════════════════════════════════════════════════════════════
# lookup_drug — request_id passed to API
# ══════════════════════════════════════════════════════════════════════════════


class TestLookupDrugRequestId:
    """FR-3: request_id is passed through to API stub."""

    @pytest.mark.asyncio
    async def test_lookup_drug_request_id_passed(self):
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch(
            "backend.app.services.drug_lookup._call_indianmedicinedb",
            return_value=None,
        ) as mock_api:
            await lookup_drug(mock_redis, "SomeDrug", request_id="req-42")

            mock_api.assert_called_once_with("SomeDrug", request_id="req-42")
