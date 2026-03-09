"""Tiered Drug Lookup — Tests for salt/composition and category matching.

20 tests covering:
- Salt normalization helpers (_normalize_salt, _extract_salt_components)
- New Redis prefix constants (SALT_REDIS_PREFIX, CATEGORY_REDIS_PREFIX)
- MEDICINE_DATA_CSV_PATH constant
- MedicineDataLoader (load_all, salt indexing, category indexing)
- load_medicine_data() convenience wrapper
- Tiered lookup_drug() — salt fallback, category fallback, ordering
- _try_redis_key helper
"""

import asyncio
import csv
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.models.schemas import DrugInfo


# ── Sample fixtures ──────────────────────────────────────────────────────────

SAMPLE_DRUG = DrugInfo(
    brand_name="Crocin",
    generic_name="Paracetamol (500mg)",
    therapeutic_class="analgesic",
    purpose_en="Reduces fever and pain",
    side_effects_en="Nausea, liver damage at high doses",
    timing_instructions="After meals",
    known_interactions="Warfarin",
)

SAMPLE_DRUG_JSON = SAMPLE_DRUG.model_dump_json()

SALT_DRUG = DrugInfo(
    brand_name="Dolo 650",
    generic_name="Paracetamol (650mg)",
    therapeutic_class="analgesic",
    purpose_en="Reduces fever",
    side_effects_en="Nausea",
    timing_instructions="",
    known_interactions="",
)

SALT_DRUG_JSON = SALT_DRUG.model_dump_json()

CATEGORY_DRUG = DrugInfo(
    brand_name="Augmentin",
    generic_name="Amoxicillin + Clavulanic Acid",
    therapeutic_class="antibiotic",
    purpose_en="Treats bacterial infections",
    side_effects_en="Diarrhea, rash",
    timing_instructions="",
    known_interactions="",
)

CATEGORY_DRUG_JSON = CATEGORY_DRUG.model_dump_json()


# ══════════════════════════════════════════════════════════════════════════════
# Test 1-2: New constants
# ══════════════════════════════════════════════════════════════════════════════


class TestNewConstants:
    def test_salt_redis_prefix(self):
        from backend.app.services.drug_lookup import SALT_REDIS_PREFIX

        assert SALT_REDIS_PREFIX == "salt:"

    def test_category_redis_prefix(self):
        from backend.app.services.drug_lookup import CATEGORY_REDIS_PREFIX

        assert CATEGORY_REDIS_PREFIX == "category:"


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: MEDICINE_DATA_CSV_PATH
# ══════════════════════════════════════════════════════════════════════════════


class TestMedicineDataPath:
    def test_medicine_data_csv_path(self):
        from backend.app.services.drug_lookup import MEDICINE_DATA_CSV_PATH

        assert isinstance(MEDICINE_DATA_CSV_PATH, Path)
        assert MEDICINE_DATA_CSV_PATH.parts[-3:] == ("data", "drugs", "medicine_data.csv")


# ══════════════════════════════════════════════════════════════════════════════
# Tests 4-6: Salt normalization helpers
# ══════════════════════════════════════════════════════════════════════════════


class TestNormalizeSalt:
    def test_normalize_salt_strips_dosage(self):
        from backend.app.services.drug_lookup import _normalize_salt

        assert _normalize_salt("Paracetamol (500mg)") == "paracetamol"
        assert _normalize_salt("Amoxicillin (250mg)") == "amoxicillin"

    def test_normalize_salt_lowercase_and_strip(self):
        from backend.app.services.drug_lookup import _normalize_salt

        assert _normalize_salt("  METFORMIN  ") == "metformin"
        assert _normalize_salt("Atorvastatin") == "atorvastatin"

    def test_extract_salt_components_multi(self):
        from backend.app.services.drug_lookup import _extract_salt_components

        components = _extract_salt_components("Paracetamol (500mg) + Caffeine (65mg)")
        assert "paracetamol" in components
        assert "caffeine" in components

    def test_extract_salt_components_empty(self):
        from backend.app.services.drug_lookup import _extract_salt_components

        assert _extract_salt_components("") == []
        assert _extract_salt_components("   ") == []

    def test_extract_salt_components_single(self):
        from backend.app.services.drug_lookup import _extract_salt_components

        components = _extract_salt_components("Paracetamol (500mg)")
        assert "paracetamol" in components


# ══════════════════════════════════════════════════════════════════════════════
# Tests 7-9: MedicineDataLoader
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def medicine_data_csv(tmp_path: Path) -> Path:
    """Create a minimal medicine_data.csv for testing."""
    csv_file = tmp_path / "medicine_data.csv"
    rows = [
        {
            "sub_category": "analgesic",
            "product_name": "Crocin Advance",
            "salt_composition": "Paracetamol (500mg)",
            "product_price": "₹30",
            "product_manufactured": "GSK",
            "medicine_desc": "Used for fever and pain relief. Take after meals.",
            "side_effects": "Nausea, liver damage",
            "drug_interactions": '{"drug": ["Warfarin"], "brand": ["Coumadin"], "effect": ["MODERATE"]}',
        },
        {
            "sub_category": "antibiotic",
            "product_name": "Augmentin 625",
            "salt_composition": "Amoxicillin (500mg) + Clavulanic Acid (125mg)",
            "product_price": "₹200",
            "product_manufactured": "GSK",
            "medicine_desc": "Treats bacterial infections.",
            "side_effects": "Diarrhea, rash",
            "drug_interactions": "",
        },
        {
            "sub_category": "analgesic",
            "product_name": "Dolo 650",
            "salt_composition": "Paracetamol (650mg)",
            "product_price": "₹25",
            "product_manufactured": "Micro Labs",
            "medicine_desc": "Reduces fever.",
            "side_effects": "Nausea",
            "drug_interactions": "",
        },
    ]
    with csv_file.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return csv_file


class TestMedicineDataLoader:
    @pytest.mark.asyncio
    async def test_load_all_returns_counts(self, medicine_data_csv):
        from backend.app.services.drug_lookup import MedicineDataLoader

        mock_redis = AsyncMock()
        loader = MedicineDataLoader(mock_redis, csv_path=medicine_data_csv)
        result = await loader.load_all()

        assert result["rows_processed"] == 3
        assert result["salts"] > 0
        assert result["categories"] > 0

    @pytest.mark.asyncio
    async def test_load_all_stores_salt_keys(self, medicine_data_csv):
        from backend.app.services.drug_lookup import MedicineDataLoader

        mock_redis = AsyncMock()
        loader = MedicineDataLoader(mock_redis, csv_path=medicine_data_csv)
        await loader.load_all()

        keys_stored = [call.args[0] for call in mock_redis.set.call_args_list]
        assert any(k.startswith("salt:") for k in keys_stored)
        # Paracetamol should be indexed as a salt component
        assert "salt:paracetamol" in keys_stored

    @pytest.mark.asyncio
    async def test_load_all_stores_category_keys(self, medicine_data_csv):
        from backend.app.services.drug_lookup import MedicineDataLoader

        mock_redis = AsyncMock()
        loader = MedicineDataLoader(mock_redis, csv_path=medicine_data_csv)
        await loader.load_all()

        keys_stored = [call.args[0] for call in mock_redis.set.call_args_list]
        assert "category:analgesic" in keys_stored
        assert "category:antibiotic" in keys_stored

    @pytest.mark.asyncio
    async def test_load_all_first_seen_salt_wins(self, medicine_data_csv):
        """First entry for a salt component should win (not overwritten by later entries)."""
        from backend.app.services.drug_lookup import MedicineDataLoader

        mock_redis = AsyncMock()
        loader = MedicineDataLoader(mock_redis, csv_path=medicine_data_csv)
        await loader.load_all()

        # Paracetamol appears in row 1 (Crocin) and row 3 (Dolo) — first should win
        salt_paracetamol_calls = [
            call for call in mock_redis.set.call_args_list
            if call.args[0] == "salt:paracetamol"
        ]
        assert len(salt_paracetamol_calls) == 1  # only stored once

    @pytest.mark.asyncio
    async def test_load_all_missing_file(self, tmp_path):
        from backend.app.services.drug_lookup import MedicineDataLoader

        mock_redis = AsyncMock()
        loader = MedicineDataLoader(mock_redis, csv_path=tmp_path / "nope.csv")
        result = await loader.load_all()

        assert result == {"salts": 0, "categories": 0, "rows_processed": 0}
        mock_redis.set.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# Test 12: load_medicine_data convenience wrapper
# ══════════════════════════════════════════════════════════════════════════════


class TestLoadMedicineDataWrapper:
    def test_load_medicine_data_is_async(self):
        from backend.app.services.drug_lookup import load_medicine_data

        assert asyncio.iscoroutinefunction(load_medicine_data)

    @pytest.mark.asyncio
    async def test_load_medicine_data_delegates(self):
        from backend.app.services.drug_lookup import load_medicine_data

        mock_redis = AsyncMock()
        with patch("backend.app.services.drug_lookup.MedicineDataLoader") as MockLoader:
            mock_instance = AsyncMock()
            mock_instance.load_all = AsyncMock(
                return_value={"salts": 10, "categories": 5, "rows_processed": 100}
            )
            MockLoader.return_value = mock_instance

            result = await load_medicine_data(mock_redis)

            MockLoader.assert_called_once_with(mock_redis)
            mock_instance.load_all.assert_awaited_once()
            assert result["salts"] == 10


# ══════════════════════════════════════════════════════════════════════════════
# Tests 14-17: Tiered lookup_drug() — salt and category fallback
# ══════════════════════════════════════════════════════════════════════════════


class TestTieredLookup:
    @pytest.mark.asyncio
    async def test_lookup_drug_salt_fallback(self):
        """When brand miss but salt hit → returns salt match."""
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()

        async def mock_get(key):
            if key == "drug:paracetamol":
                return None  # brand miss
            if key == "salt:paracetamol":
                return SALT_DRUG_JSON  # salt hit
            return None

        mock_redis.get = AsyncMock(side_effect=mock_get)

        result = await lookup_drug(mock_redis, "Paracetamol", request_id="req-1")

        assert result is not None
        assert result.brand_name == "Dolo 650"

    @pytest.mark.asyncio
    async def test_lookup_drug_category_fallback(self):
        """When brand + salt miss but category hit → returns category match."""
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()

        async def mock_get(key):
            if key == "category:antibiotic":
                return CATEGORY_DRUG_JSON
            return None

        mock_redis.get = AsyncMock(side_effect=mock_get)

        result = await lookup_drug(mock_redis, "Antibiotic", request_id="req-2")

        assert result is not None
        assert result.therapeutic_class == "antibiotic"

    @pytest.mark.asyncio
    async def test_lookup_drug_brand_wins_over_salt(self):
        """Brand match takes priority over salt match."""
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()

        async def mock_get(key):
            if key == "drug:paracetamol":
                return SAMPLE_DRUG_JSON  # brand hit (Crocin)
            if key == "salt:paracetamol":
                return SALT_DRUG_JSON  # salt hit (Dolo)
            return None

        mock_redis.get = AsyncMock(side_effect=mock_get)

        result = await lookup_drug(mock_redis, "Paracetamol")

        assert result is not None
        assert result.brand_name == "Crocin"  # brand wins

    @pytest.mark.asyncio
    async def test_lookup_drug_all_levels_miss(self):
        """All levels miss → returns None (with API also returning None)."""
        from backend.app.services.drug_lookup import lookup_drug

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch(
            "backend.app.services.drug_lookup._call_indianmedicinedb",
            return_value=None,
        ):
            result = await lookup_drug(mock_redis, "UnknownDrug123")

        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# Tests 18-19: _try_redis_key helper
# ══════════════════════════════════════════════════════════════════════════════


class TestTryRedisKey:
    @pytest.mark.asyncio
    async def test_try_redis_key_hit(self):
        from backend.app.services.drug_lookup import _try_redis_key

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=SAMPLE_DRUG_JSON)

        result = await _try_redis_key(mock_redis, "drug:crocin", "Test")

        assert result is not None
        assert result.brand_name == "Crocin"

    @pytest.mark.asyncio
    async def test_try_redis_key_miss(self):
        from backend.app.services.drug_lookup import _try_redis_key

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        result = await _try_redis_key(mock_redis, "drug:nonexistent", "Test")

        assert result is None

    @pytest.mark.asyncio
    async def test_try_redis_key_error_resilience(self):
        from backend.app.services.drug_lookup import _try_redis_key

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))

        result = await _try_redis_key(mock_redis, "drug:test", "Test")

        assert result is None  # Never raises
