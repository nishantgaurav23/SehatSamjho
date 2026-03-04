"""S8.2 — Load Drug CSV: 20 tests.

Tests for DRUG_CSV_PATH, DRUG_REDIS_PREFIX, DrugCSVLoader, and load_drug_csv().
All Redis calls mocked — no real I/O.
"""

import asyncio
import csv
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.services.drug_lookup import (
    DRUG_CSV_PATH,
    DRUG_REDIS_PREFIX,
    DrugCSVLoader,
    load_drug_csv,
)
from backend.app.models.schemas import DrugInfo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_redis():
    """Async mock Redis client with .set() method."""
    client = AsyncMock()
    client.set = AsyncMock()
    return client


@pytest.fixture()
def valid_csv(tmp_path: Path) -> Path:
    """Create a minimal valid CSV file matching medicines.csv schema."""
    csv_file = tmp_path / "medicines.csv"
    rows = [
        {
            "brand_name": "Crocin",
            "generic_name": "paracetamol",
            "therapeutic_class": "analgesic",
            "purpose_en": "Reduces fever",
            "side_effects_en": "Nausea",
            "timing_instructions": "After meals",
            "known_interactions": "Avoid alcohol",
        },
        {
            "brand_name": "Azithral",
            "generic_name": "azithromycin",
            "therapeutic_class": "antibiotic",
            "purpose_en": "Treats infections",
            "side_effects_en": "Diarrhea",
            "timing_instructions": "Before meals",
            "known_interactions": "Avoid antacids",
        },
    ]
    with csv_file.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return csv_file


@pytest.fixture()
def csv_with_empty_generic(tmp_path: Path) -> Path:
    """CSV where one row has empty generic_name."""
    csv_file = tmp_path / "medicines.csv"
    rows = [
        {
            "brand_name": "BrandOnly",
            "generic_name": "",
            "therapeutic_class": "other",
            "purpose_en": "Purpose",
            "side_effects_en": "None",
            "timing_instructions": "Any time",
            "known_interactions": "None",
        },
    ]
    with csv_file.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return csv_file


@pytest.fixture()
def csv_with_invalid_row(tmp_path: Path) -> Path:
    """CSV where one row is missing brand_name."""
    csv_file = tmp_path / "medicines.csv"
    rows = [
        {
            "brand_name": "",
            "generic_name": "orphan",
            "therapeutic_class": "other",
            "purpose_en": "Purpose",
            "side_effects_en": "None",
            "timing_instructions": "Any",
            "known_interactions": "None",
        },
    ]
    with csv_file.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return csv_file


@pytest.fixture()
def csv_with_duplicates(tmp_path: Path) -> Path:
    """CSV where two rows normalize to the same brand name."""
    csv_file = tmp_path / "medicines.csv"
    rows = [
        {
            "brand_name": "Crocin",
            "generic_name": "paracetamol",
            "therapeutic_class": "analgesic",
            "purpose_en": "First",
            "side_effects_en": "None",
            "timing_instructions": "Morning",
            "known_interactions": "None",
        },
        {
            "brand_name": "  CROCIN  ",
            "generic_name": "paracetamol",
            "therapeutic_class": "analgesic",
            "purpose_en": "Second",
            "side_effects_en": "None",
            "timing_instructions": "Evening",
            "known_interactions": "None",
        },
    ]
    with csv_file.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return csv_file


@pytest.fixture()
def csv_with_whitespace(tmp_path: Path) -> Path:
    """CSV with uppercase and whitespace in names."""
    csv_file = tmp_path / "medicines.csv"
    rows = [
        {
            "brand_name": "  DOLO 650  ",
            "generic_name": "  Paracetamol 650mg  ",
            "therapeutic_class": "analgesic",
            "purpose_en": "Reduces fever",
            "side_effects_en": "Nausea",
            "timing_instructions": "After meals",
            "known_interactions": "Avoid alcohol",
        },
    ]
    with csv_file.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return csv_file


# ===========================================================================
# Constants (pure, no mocking)
# ===========================================================================


class TestConstants:
    """Tests 1–4: DRUG_CSV_PATH and DRUG_REDIS_PREFIX."""

    def test_drug_csv_path_is_path(self):
        assert isinstance(DRUG_CSV_PATH, Path)

    def test_drug_csv_path_ends_with_medicines_csv(self):
        assert DRUG_CSV_PATH.parts[-3:] == ("data", "drugs", "medicines.csv")

    def test_drug_redis_prefix_value(self):
        assert DRUG_REDIS_PREFIX == "drug:"

    def test_drug_redis_prefix_is_string(self):
        assert isinstance(DRUG_REDIS_PREFIX, str)


# ===========================================================================
# DrugCSVLoader constructor
# ===========================================================================


class TestDrugCSVLoaderConstructor:
    """Tests 5–7: Constructor."""

    def test_loader_accepts_redis_client(self, mock_redis):
        loader = DrugCSVLoader(mock_redis)
        assert loader._redis is mock_redis

    def test_loader_default_csv_path(self, mock_redis):
        loader = DrugCSVLoader(mock_redis)
        assert loader._csv_path == DRUG_CSV_PATH

    def test_loader_custom_csv_path(self, mock_redis, tmp_path):
        custom = tmp_path / "custom.csv"
        loader = DrugCSVLoader(mock_redis, csv_path=custom)
        assert loader._csv_path == custom


# ===========================================================================
# _load_csv() method
# ===========================================================================


class TestLoadCSV:
    """Tests 8–16: _load_csv() with mocked Redis."""

    @pytest.mark.asyncio
    async def test_load_csv_reads_valid_file(self, mock_redis, valid_csv):
        loader = DrugCSVLoader(mock_redis, csv_path=valid_csv)
        count = await loader._load_csv()
        assert count == 2

    @pytest.mark.asyncio
    async def test_load_csv_stores_brand_key(self, mock_redis, valid_csv):
        loader = DrugCSVLoader(mock_redis, csv_path=valid_csv)
        await loader._load_csv()
        # Check redis.set was called with drug:crocin
        keys_stored = [call.args[0] for call in mock_redis.set.call_args_list]
        assert "drug:crocin" in keys_stored

    @pytest.mark.asyncio
    async def test_load_csv_stores_generic_key(self, mock_redis, valid_csv):
        loader = DrugCSVLoader(mock_redis, csv_path=valid_csv)
        await loader._load_csv()
        keys_stored = [call.args[0] for call in mock_redis.set.call_args_list]
        assert "drug:paracetamol" in keys_stored

    @pytest.mark.asyncio
    async def test_load_csv_normalizes_names(self, mock_redis, csv_with_whitespace):
        loader = DrugCSVLoader(mock_redis, csv_path=csv_with_whitespace)
        await loader._load_csv()
        keys_stored = [call.args[0] for call in mock_redis.set.call_args_list]
        assert "drug:dolo 650" in keys_stored
        assert "drug:paracetamol 650mg" in keys_stored

    @pytest.mark.asyncio
    async def test_load_csv_value_is_druginfo_json(self, mock_redis, valid_csv):
        loader = DrugCSVLoader(mock_redis, csv_path=valid_csv)
        await loader._load_csv()
        # Find the call for drug:crocin and parse the value
        for call in mock_redis.set.call_args_list:
            if call.args[0] == "drug:crocin":
                raw_json = call.args[1]
                parsed = DrugInfo.model_validate_json(raw_json)
                assert parsed.brand_name == "Crocin"
                assert parsed.generic_name == "paracetamol"
                return
        pytest.fail("drug:crocin key not found in redis.set calls")

    @pytest.mark.asyncio
    async def test_load_csv_skips_invalid_row(self, mock_redis, csv_with_invalid_row):
        loader = DrugCSVLoader(mock_redis, csv_path=csv_with_invalid_row)
        count = await loader._load_csv()
        assert count == 0
        mock_redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_csv_file_not_found(self, mock_redis, tmp_path):
        missing = tmp_path / "nope.csv"
        loader = DrugCSVLoader(mock_redis, csv_path=missing)
        with pytest.raises(FileNotFoundError):
            await loader._load_csv()

    @pytest.mark.asyncio
    async def test_load_csv_empty_generic_only_brand_key(self, mock_redis, csv_with_empty_generic):
        loader = DrugCSVLoader(mock_redis, csv_path=csv_with_empty_generic)
        await loader._load_csv()
        keys_stored = [call.args[0] for call in mock_redis.set.call_args_list]
        assert "drug:brandonly" in keys_stored
        # No generic key should be stored
        assert len(keys_stored) == 1

    @pytest.mark.asyncio
    async def test_load_csv_duplicate_names_last_wins(self, mock_redis, csv_with_duplicates):
        loader = DrugCSVLoader(mock_redis, csv_path=csv_with_duplicates)
        count = await loader._load_csv()
        assert count == 2
        # Both rows are "loaded" — later redis.set overwrites earlier for same key
        crocin_calls = [
            call for call in mock_redis.set.call_args_list if call.args[0] == "drug:crocin"
        ]
        assert len(crocin_calls) == 2  # both writes happen, last wins
        # The last value written should be "Second"
        last_json = crocin_calls[-1].args[1]
        parsed = DrugInfo.model_validate_json(last_json)
        assert parsed.purpose_en == "Second"


# ===========================================================================
# load_all() method
# ===========================================================================


class TestLoadAll:
    """Tests 17–18: load_all() delegates and logs."""

    @pytest.mark.asyncio
    async def test_load_all_returns_count(self, mock_redis, valid_csv):
        loader = DrugCSVLoader(mock_redis, csv_path=valid_csv)
        result = await loader.load_all()
        assert result == 2

    @pytest.mark.asyncio
    async def test_load_all_logs_summary(self, mock_redis, valid_csv, capfd):
        """load_all() logs the summary (we just verify it runs without error)."""
        loader = DrugCSVLoader(mock_redis, csv_path=valid_csv)
        result = await loader.load_all()
        assert isinstance(result, int)


# ===========================================================================
# load_drug_csv() module-level function
# ===========================================================================


class TestLoadDrugCSV:
    """Tests 19–20: load_drug_csv() convenience wrapper."""

    def test_load_drug_csv_is_async(self):
        assert asyncio.iscoroutinefunction(load_drug_csv)

    @pytest.mark.asyncio
    async def test_load_drug_csv_delegates_to_loader(self, mock_redis, valid_csv):
        with patch("backend.app.services.drug_lookup.DrugCSVLoader") as MockLoader:
            mock_instance = AsyncMock()
            mock_instance.load_all = AsyncMock(return_value=5)
            MockLoader.return_value = mock_instance

            result = await load_drug_csv(mock_redis)

            MockLoader.assert_called_once_with(mock_redis)
            mock_instance.load_all.assert_awaited_once()
            assert result == 5
