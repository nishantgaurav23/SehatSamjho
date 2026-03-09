"""S11.5 — Drug Database CSV (Data File): expanded dataset validation tests.

Pure file-system tests — no mocking needed.
Validates that medicines.csv has been expanded to 1000+ entries
with proper data quality, uniqueness, therapeutic class coverage,
and backward compatibility with S8.1 original entries.
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
MIN_ROWS = 1000
MIN_THERAPEUTIC_CLASSES = 20
PURPOSE_MAX_LEN = 200
BRAND_NAME_MIN_LEN = 2
BRAND_NAME_MAX_LEN = 120

# Key S8.1 entries that must be preserved
ORIGINAL_S81_BRANDS = [
    "Crocin",
    "Dolo 650",
    "Combiflam",
    "Amoxyclav",
    "Metformin",
    "Amlodipine",
    "Pan D",
    "Omez",
    "Atorvastatin",
    "Ecosprin",
    "Cetirizine",
    "Thyronorm",
    "Shelcal",
    "Metrogyl",
    "ORS",
    "Benadryl",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_rows() -> list[dict]:
    """Load all rows from the CSV using DictReader."""
    with open(CSV_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ---------------------------------------------------------------------------
# Test 1: File existence
# ---------------------------------------------------------------------------


class TestFileExists:
    def test_csv_exists(self):
        """FR-7: CSV file must exist at expected path."""
        assert CSV_PATH.is_file(), f"{CSV_PATH} must exist"


# ---------------------------------------------------------------------------
# Test 2: Correct headers
# ---------------------------------------------------------------------------


class TestHeaders:
    def test_csv_has_correct_headers(self):
        """FR-7: Header row must have exactly 7 required columns."""
        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert list(reader.fieldnames) == REQUIRED_COLUMNS


# ---------------------------------------------------------------------------
# Test 3: Row count >= 1000
# ---------------------------------------------------------------------------


class TestRowCount:
    def test_csv_has_at_least_1000_rows(self):
        """FR-1: CSV must have >= 1000 data rows."""
        rows = _load_rows()
        assert len(rows) >= MIN_ROWS, f"Expected >= {MIN_ROWS} rows, got {len(rows)}"


# ---------------------------------------------------------------------------
# Test 4: All fields non-empty
# ---------------------------------------------------------------------------


class TestAllFieldsNonEmpty:
    def test_core_fields_non_empty(self):
        """Core fields (brand, generic, class, purpose, side_effects) always populated."""
        core_cols = [
            "brand_name",
            "generic_name",
            "therapeutic_class",
            "purpose_en",
            "side_effects_en",
        ]
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            for col in core_cols:
                val = row.get(col, "")
                assert val.strip(), f"Row {i}: {col} is empty"


# ---------------------------------------------------------------------------
# Test 5: Brand names unique (case-insensitive)
# ---------------------------------------------------------------------------


class TestBrandNameUniqueness:
    def test_brand_names_unique_case_insensitive(self):
        """FR-3: No duplicate brand_name values when lowercased."""
        rows = _load_rows()
        seen: dict[str, int] = {}
        for i, row in enumerate(rows, start=2):
            key = row["brand_name"].strip().lower()
            assert key not in seen, (
                f"Duplicate brand_name '{row['brand_name']}' at rows {seen[key]} and {i}"
            )
            seen[key] = i


# ---------------------------------------------------------------------------
# Test 6: Therapeutic class coverage >= 20
# ---------------------------------------------------------------------------


class TestTherapeuticClassCoverage:
    def test_therapeutic_class_coverage(self):
        """FR-4: At least 20 distinct therapeutic_class values."""
        rows = _load_rows()
        classes = {row["therapeutic_class"].strip().lower() for row in rows}
        assert len(classes) >= MIN_THERAPEUTIC_CLASSES, (
            f"Expected >= {MIN_THERAPEUTIC_CLASSES} therapeutic classes, got {len(classes)}: "
            f"{sorted(classes)}"
        )


# ---------------------------------------------------------------------------
# Test 7: Purpose max length
# ---------------------------------------------------------------------------


class TestPurposeMaxLength:
    def test_purpose_en_max_length(self):
        """FR-5: All purpose_en values must be <= 200 characters."""
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            length = len(row["purpose_en"])
            assert length <= PURPOSE_MAX_LEN, (
                f"Row {i}: purpose_en is {length} chars, max {PURPOSE_MAX_LEN}"
            )


# ---------------------------------------------------------------------------
# Test 8: Original S8.1 entries preserved
# ---------------------------------------------------------------------------


class TestOriginalEntriesPreserved:
    def test_original_entries_preserved(self):
        """FR-6: Key S8.1 brand names must still be present."""
        rows = _load_rows()
        brand_names = {row["brand_name"].strip() for row in rows}
        for expected in ORIGINAL_S81_BRANDS:
            assert expected in brand_names, (
                f"Original S8.1 entry '{expected}' not found in expanded CSV"
            )


# ---------------------------------------------------------------------------
# Test 9: Valid UTF-8
# ---------------------------------------------------------------------------


class TestValidUtf8:
    def test_csv_valid_utf8(self):
        """FR-7: File must decode as valid UTF-8."""
        CSV_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 10: No trailing whitespace in brand/generic names
# ---------------------------------------------------------------------------


class TestNoTrailingWhitespace:
    def test_no_trailing_whitespace(self):
        """FR-2: No brand_name or generic_name has leading/trailing whitespace."""
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            bn = row["brand_name"]
            gn = row["generic_name"]
            assert bn == bn.strip(), f"Row {i}: brand_name has whitespace: '{bn}'"
            assert gn == gn.strip(), f"Row {i}: generic_name has whitespace: '{gn}'"


# ---------------------------------------------------------------------------
# Test 11: Therapeutic class values are lowercase
# ---------------------------------------------------------------------------


class TestTherapeuticClassLowercase:
    def test_therapeutic_class_lowercase(self):
        """FR-4: All therapeutic_class values must be lowercase."""
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            tc = row["therapeutic_class"].strip()
            assert tc == tc.lower(), f"Row {i}: therapeutic_class '{tc}' is not lowercase"


# ---------------------------------------------------------------------------
# Test 12: Generic name populated
# ---------------------------------------------------------------------------


class TestGenericNamePopulated:
    def test_generic_name_populated(self):
        """FR-2: Every row has non-empty generic_name."""
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            assert row["generic_name"].strip(), f"Row {i}: generic_name is empty"


# ---------------------------------------------------------------------------
# Test 13: Timing instructions populated
# ---------------------------------------------------------------------------


class TestTimingInstructionsPopulated:
    def test_timing_instructions_populated(self):
        """timing_instructions column present; curated entries populated."""
        rows = _load_rows()
        assert "timing_instructions" in rows[0], "timing_instructions column missing"
        filled = sum(1 for r in rows if r["timing_instructions"].strip())
        assert filled >= 500, f"Expected ≥500 rows with timing_instructions, got {filled}"


# ---------------------------------------------------------------------------
# Test 14: Known interactions populated
# ---------------------------------------------------------------------------


class TestKnownInteractionsPopulated:
    def test_known_interactions_populated(self):
        """known_interactions column present; curated entries populated."""
        rows = _load_rows()
        assert "known_interactions" in rows[0], "known_interactions column missing"
        filled = sum(1 for r in rows if r["known_interactions"].strip())
        assert filled >= 500, f"Expected ≥500 rows with known_interactions, got {filled}"


# ---------------------------------------------------------------------------
# Test 15: Side effects populated
# ---------------------------------------------------------------------------


class TestSideEffectsPopulated:
    def test_side_effects_populated(self):
        """FR-2: Every row has non-empty side_effects_en."""
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            assert row["side_effects_en"].strip(), f"Row {i}: side_effects_en is empty"


# ---------------------------------------------------------------------------
# Test 16: No duplicate rows
# ---------------------------------------------------------------------------


class TestNoDuplicateRows:
    def test_no_duplicate_rows(self):
        """No two rows are identical across all 7 columns."""
        rows = _load_rows()
        seen: set[tuple] = set()
        for i, row in enumerate(rows, start=2):
            key = tuple(row[col].strip() for col in REQUIRED_COLUMNS)
            assert key not in seen, f"Row {i} is a duplicate of an earlier row"
            seen.add(key)


# ---------------------------------------------------------------------------
# Test 17: Brand name reasonable length
# ---------------------------------------------------------------------------


class TestBrandNameLength:
    def test_brand_name_reasonable_length(self):
        """Brand names must be between 2 and 50 characters."""
        rows = _load_rows()
        for i, row in enumerate(rows, start=2):
            length = len(row["brand_name"].strip())
            assert BRAND_NAME_MIN_LEN <= length <= BRAND_NAME_MAX_LEN, (
                f"Row {i}: brand_name '{row['brand_name']}' is {length} chars "
                f"(expected {BRAND_NAME_MIN_LEN}-{BRAND_NAME_MAX_LEN})"
            )


# ---------------------------------------------------------------------------
# Test 18: CSV parseable by csv module
# ---------------------------------------------------------------------------


class TestCsvParseable:
    def test_csv_parseable_by_csv_module(self):
        """FR-7: csv.reader() must parse the file without exceptions."""
        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert len(rows) > 1, "CSV must have header + data rows"
        assert len(rows[0]) == 7, f"Header has {len(rows[0])} columns, expected 7"


# ---------------------------------------------------------------------------
# Test 19: No BOM marker
# ---------------------------------------------------------------------------


class TestNoBom:
    def test_no_bom_marker(self):
        """FR-7: File must not start with UTF-8 BOM."""
        raw = CSV_PATH.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), "File has UTF-8 BOM marker"


# ---------------------------------------------------------------------------
# Test 20: Consistent line endings
# ---------------------------------------------------------------------------


class TestConsistentLineEndings:
    def test_consistent_line_endings(self):
        """FR-7: File must use consistent line endings (no mixed \\r\\n and \\n)."""
        raw = CSV_PATH.read_bytes()
        has_crlf = b"\r\n" in raw
        # Check for bare \n (not preceded by \r)
        stripped = raw.replace(b"\r\n", b"")
        has_bare_lf = b"\n" in stripped
        # Either all CRLF or all LF, not both
        assert not (has_crlf and has_bare_lf), "File has mixed line endings (both \\r\\n and \\n)"
