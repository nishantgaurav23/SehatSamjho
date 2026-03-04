"""S8.1 — Drug Database CSV: static file validation tests.

Pure file-system tests — no mocking needed.
Validates structure, column headers, data quality, uniqueness,
and category coverage of the curated medicines CSV.
"""

import csv
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CSV_PATH = Path(__file__).resolve().parents[3] / "data" / "drugs" / "medicines.csv"
REQUIRED_COLUMNS = [
    "brand_name",
    "generic_name",
    "therapeutic_class",
    "purpose_en",
    "side_effects_en",
    "timing_instructions",
    "known_interactions",
]
MIN_ROWS = 50
PURPOSE_MAX_LEN = 200
MIN_CATEGORIES = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_rows() -> list[dict]:
    """Load all rows from the CSV using DictReader."""
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ---------------------------------------------------------------------------
# Phase 1: File existence and encoding (tests 1-2)
# ---------------------------------------------------------------------------


class TestFileExistsAndEncoding:
    """CSV file must exist and be valid UTF-8."""

    def test_csv_file_exists(self):
        assert CSV_PATH.is_file(), f"{CSV_PATH} must exist"

    def test_csv_utf8_encoding(self):
        # Must be readable as UTF-8 without errors
        content = CSV_PATH.read_text(encoding="utf-8")
        # No BOM
        assert not content.startswith("\ufeff"), "File must not have a UTF-8 BOM"


# ---------------------------------------------------------------------------
# Phase 2: Header validation (tests 3-4)
# ---------------------------------------------------------------------------


class TestHeaderValidation:
    """CSV header row must have exactly 7 required columns in order."""

    def test_csv_header_columns(self):
        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames is not None
            assert set(reader.fieldnames) == set(REQUIRED_COLUMNS)

    def test_csv_header_order(self):
        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert list(reader.fieldnames) == REQUIRED_COLUMNS


# ---------------------------------------------------------------------------
# Phase 3: Row count and empty rows (tests 5, 17)
# ---------------------------------------------------------------------------


class TestRowCount:
    """Minimum row count and no all-empty rows."""

    def test_csv_minimum_row_count(self):
        rows = _load_rows()
        assert len(rows) >= MIN_ROWS, f"Expected >= {MIN_ROWS} rows, got {len(rows)}"

    def test_csv_no_empty_rows(self):
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):  # row 1 is header
            values = [v.strip() for v in row.values() if v is not None]
            assert any(values), f"Row {i} has all empty fields"


# ---------------------------------------------------------------------------
# Phase 4: Required field validation (tests 6-13)
# ---------------------------------------------------------------------------


class TestRequiredFields:
    """All required fields must be present and non-empty."""

    def test_csv_brand_name_non_empty(self):
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            assert row["brand_name"].strip(), f"Row {i}: brand_name is empty"

    def test_csv_brand_name_stripped(self):
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            val = row["brand_name"]
            assert val == val.strip(), f"Row {i}: brand_name has leading/trailing whitespace"

    def test_csv_generic_name_non_empty(self):
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            assert row["generic_name"].strip(), f"Row {i}: generic_name is empty"

    def test_csv_therapeutic_class_non_empty(self):
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            assert row["therapeutic_class"].strip(), f"Row {i}: therapeutic_class is empty"

    def test_csv_purpose_en_non_empty(self):
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            assert row["purpose_en"].strip(), f"Row {i}: purpose_en is empty"

    def test_csv_purpose_en_max_length(self):
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            assert len(row["purpose_en"]) <= PURPOSE_MAX_LEN, (
                f"Row {i}: purpose_en exceeds {PURPOSE_MAX_LEN} chars "
                f"({len(row['purpose_en'])} chars)"
            )

    def test_csv_side_effects_non_empty(self):
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            assert row["side_effects_en"].strip(), f"Row {i}: side_effects_en is empty"

    def test_csv_timing_instructions_non_empty(self):
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            assert row["timing_instructions"].strip(), f"Row {i}: timing_instructions is empty"


# ---------------------------------------------------------------------------
# Phase 5: Data quality (tests 14-16, 18-20)
# ---------------------------------------------------------------------------


class TestDataQuality:
    """Data quality: known_interactions column, uniqueness, categories, field counts."""

    def test_csv_known_interactions_column_exists(self):
        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert "known_interactions" in reader.fieldnames

    def test_csv_no_duplicate_brand_names(self):
        rows = _load_rows()
        seen: dict[str, int] = {}
        for i, row in enumerate(rows, start=2):
            key = row["brand_name"].strip().lower()
            assert (
                key not in seen
            ), f"Duplicate brand_name '{row['brand_name']}' at rows {seen[key]} and {i}"
            seen[key] = i

    def test_csv_parseable_by_dictreader(self):
        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) > 0, "DictReader returned no rows"

    def test_csv_covers_common_categories(self):
        rows = _load_rows()
        categories = {row["therapeutic_class"].strip().lower() for row in rows}
        assert (
            len(categories) >= MIN_CATEGORIES
        ), f"Expected >= {MIN_CATEGORIES} distinct therapeutic classes, got {len(categories)}"

    def test_csv_brand_name_no_duplicates_with_generic(self):
        """brand_name and generic_name should be different fields."""
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            bn = row["brand_name"].strip().lower()
            gn = row["generic_name"].strip().lower()
            assert bn != gn, f"Row {i}: brand_name '{row['brand_name']}' same as generic_name"

    def test_csv_row_field_count(self):
        """Every row must have exactly 7 fields (no missing/extra columns)."""
        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert len(header) == 7, f"Header has {len(header)} columns, expected 7"
            for i, row in enumerate(reader, start=2):
                assert len(row) == 7, f"Row {i} has {len(row)} fields, expected 7"
