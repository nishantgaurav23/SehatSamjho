# Spec S11.5 — Drug Database CSV (Data File)

## Overview
Expand the curated `data/drugs/medicines.csv` from ~66 entries (created in S8.1) to 1000 most-prescribed Indian medicines. The CSV uses the same 7-column schema established in S8.1 (brand_name, generic_name, therapeutic_class, purpose_en, side_effects_en, timing_instructions, known_interactions). Data is manually curated or sourced from open datasets (public domain / OpenFDA-equivalent Indian data). This file is loaded into Redis at startup via `make seed` (S11.7) and queried by `lookup_drug()` (S8.3).

## Dependencies
- **S8.1** (Drug database CSV schema) — defines column headers, validation rules, and initial data

## Target Location
- `data/drugs/medicines.csv`

---

## Functional Requirements

### FR-1: CSV contains 1000 entries
- **What**: The CSV file must contain at least 1000 rows (excluding the header row), each representing a distinct Indian medicine
- **Inputs**: None (static data file)
- **Outputs**: CSV file with 1000+ data rows
- **Edge cases**: No duplicate brand_name entries; each row must have all 7 columns populated (no empty fields)

### FR-2: All 7 columns populated for every row
- **What**: Every row must have non-empty values for: brand_name, generic_name, therapeutic_class, purpose_en, side_effects_en, timing_instructions, known_interactions
- **Inputs**: CSV row data
- **Outputs**: No blank cells
- **Edge cases**: Fields with commas must be properly quoted; no trailing/leading whitespace in field values

### FR-3: Brand names are unique
- **What**: No two rows share the same brand_name (case-insensitive)
- **Inputs**: brand_name column
- **Outputs**: All brand names are distinct
- **Edge cases**: Different dosage strengths of the same brand (e.g., "Dolo 650" vs "Dolo 1000") count as separate entries

### FR-4: Broad therapeutic class coverage
- **What**: The dataset must cover at least 20 distinct therapeutic classes, representing the breadth of commonly prescribed Indian medicines
- **Inputs**: therapeutic_class column
- **Outputs**: >= 20 unique therapeutic classes
- **Edge cases**: Therapeutic class names should be lowercase and consistent (e.g., always "antibiotic" not sometimes "Antibiotic")

### FR-5: Purpose descriptions are patient-friendly
- **What**: The `purpose_en` field must be written in plain English that a patient can understand (no medical jargon without context). Each description should be <= 200 characters
- **Inputs**: purpose_en column
- **Outputs**: Clear, concise plain-language descriptions
- **Edge cases**: Descriptions should not start with "Used for" repetitively; vary the phrasing

### FR-6: Existing S8.1 entries preserved
- **What**: All 66 entries from the S8.1 CSV must remain in the expanded dataset (backward compatibility). No data should be lost or altered from the original prototype entries
- **Inputs**: Original 66 rows from S8.1
- **Outputs**: All 66 present in expanded file
- **Edge cases**: If corrections to original data are needed, document them

### FR-7: CSV is valid and parseable
- **What**: The file must be valid UTF-8 CSV, parseable by Python's `csv.reader()` without errors. No BOM markers, consistent line endings
- **Inputs**: Raw file
- **Outputs**: Successfully parsed by csv module
- **Edge cases**: Fields containing commas, quotes, or newlines must follow RFC 4180 quoting rules

---

## Tangible Outcomes

- [ ] **Outcome 1**: `data/drugs/medicines.csv` contains >= 1000 data rows + 1 header row
- [ ] **Outcome 2**: All 7 columns are non-empty for every row
- [ ] **Outcome 3**: No duplicate brand_name values (case-insensitive)
- [ ] **Outcome 4**: At least 20 distinct therapeutic_class values
- [ ] **Outcome 5**: All purpose_en values are <= 200 characters
- [ ] **Outcome 6**: Original 66 S8.1 entries are present and intact
- [ ] **Outcome 7**: File is valid UTF-8 CSV parseable by `csv.reader()`
- [ ] **Outcome 8**: Existing S8.1 tests (`backend/tests/data/test_drug_csv.py`) still pass (MIN_ROWS=50 threshold met)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_csv_exists**: File exists at `data/drugs/medicines.csv`
2. **test_csv_has_correct_headers**: Header row matches 7 required columns
3. **test_csv_has_at_least_1000_rows**: Row count >= 1000 (upgraded from S8.1's MIN_ROWS=50)
4. **test_all_fields_non_empty**: Every cell in every row is non-empty after stripping whitespace
5. **test_brand_names_unique_case_insensitive**: No duplicate brand_name values when lowercased
6. **test_therapeutic_class_coverage**: >= 20 distinct therapeutic_class values
7. **test_purpose_en_max_length**: All purpose_en values <= 200 characters
8. **test_original_entries_preserved**: Spot-check that key S8.1 entries (Crocin, Dolo 650, Amoxyclav, Metformin, etc.) are present
9. **test_csv_valid_utf8**: File decodes as UTF-8 without errors
10. **test_no_trailing_whitespace**: No brand_name or generic_name has leading/trailing whitespace
11. **test_therapeutic_class_lowercase**: All therapeutic_class values are lowercase
12. **test_generic_name_populated**: Every row has a non-empty generic_name
13. **test_timing_instructions_populated**: Every row has non-empty timing_instructions
14. **test_known_interactions_populated**: Every row has non-empty known_interactions
15. **test_side_effects_populated**: Every row has non-empty side_effects_en
16. **test_no_duplicate_rows**: No two rows are identical across all 7 columns
17. **test_brand_name_reasonable_length**: All brand names are between 2 and 50 characters
18. **test_csv_parseable_by_csv_module**: `csv.reader()` parses the file without exceptions
19. **test_no_bom_marker**: File does not start with UTF-8 BOM (0xEF 0xBB 0xBF)
20. **test_consistent_line_endings**: File uses consistent line endings (no mixed \r\n and \n)

### Mocking Strategy
- No mocking needed — this is a static file validation spec (same pattern as S8.1)

### Coverage Expectation
- All tests are pure file-system assertions against `data/drugs/medicines.csv`
- Tests validate data quality, not runtime behavior

---

## References
- `roadmap.md` — Phase 11: Infra & Seeding
- `specs/spec-S8.1-drug-csv/` — original CSV schema and initial 66-entry dataset
- `backend/tests/data/test_drug_csv.py` — existing S8.1 validation tests (20 tests)
- `backend/app/services/drug_lookup.py` — consumer of this CSV (load_drug_csv, lookup_drug)
