# Spec S8.1 — Drug Database CSV

## Overview
A curated CSV file containing the ~1000 most-prescribed Indian medicines. This is the foundational data source for the drug lookup service (Phase 8). Each row provides structured information about a medicine — brand name, generic name, therapeutic class, plain-English purpose, common side effects, timing instructions, and known interactions. The CSV is loaded into Redis at startup (S8.2) and used to enrich extracted prescription data before translation.

## Dependencies
None — this is a standalone data file with no code dependencies.

## Target Location
`data/drugs/medicines.csv`

---

## Functional Requirements

### FR-1: CSV file exists at correct path
- **What**: A well-formed CSV file must exist at `data/drugs/medicines.csv`
- **Inputs**: None (static file)
- **Outputs**: File on disk
- **Edge cases**: File must be UTF-8 encoded, no BOM

### FR-2: Required columns present with correct headers
- **What**: The CSV must have exactly these 7 columns as the header row: `brand_name`, `generic_name`, `therapeutic_class`, `purpose_en`, `side_effects_en`, `timing_instructions`, `known_interactions`
- **Inputs**: First row of CSV
- **Outputs**: Header validation passes
- **Edge cases**: Column order matters; no extra unnamed columns; headers must be lowercase with underscores

### FR-3: Minimum row count
- **What**: The CSV must contain at least 50 medicine entries (rows excluding header) for the prototype. Target is ~1000 but prototype minimum is 50.
- **Inputs**: Row count
- **Outputs**: Count >= 50
- **Edge cases**: Empty rows (all blank fields) should not count

### FR-4: brand_name column — non-empty, normalized
- **What**: Every row must have a non-empty `brand_name`. Brand names should be title-cased (e.g., "Crocin", "Dolo 650").
- **Inputs**: brand_name field per row
- **Outputs**: Validated non-empty strings
- **Edge cases**: Leading/trailing whitespace must be stripped; no duplicate brand names

### FR-5: generic_name column — non-empty
- **What**: Every row must have a non-empty `generic_name` (the active pharmaceutical ingredient). Lowercase (e.g., "paracetamol", "amoxicillin").
- **Inputs**: generic_name field per row
- **Outputs**: Validated non-empty strings
- **Edge cases**: Multiple generics separated by " + " (e.g., "amoxicillin + clavulanic acid")

### FR-6: therapeutic_class column — non-empty, from known set
- **What**: Every row must have a non-empty `therapeutic_class` describing the drug category (e.g., "analgesic", "antibiotic", "antihypertensive").
- **Inputs**: therapeutic_class field per row
- **Outputs**: Validated non-empty strings
- **Edge cases**: Should be lowercase; common classes include analgesic, antibiotic, antihypertensive, antidiabetic, antacid, etc.

### FR-7: purpose_en column — plain English, non-empty
- **What**: Every row must have a `purpose_en` field with a brief plain-English description of what the medicine is used for (e.g., "Reduces fever and relieves mild to moderate pain").
- **Inputs**: purpose_en field per row
- **Outputs**: Validated non-empty strings, max 200 characters
- **Edge cases**: Must be patient-friendly language, not clinical jargon

### FR-8: side_effects_en column — non-empty
- **What**: Every row must have a `side_effects_en` field listing common side effects in plain English (e.g., "Nausea, stomach upset, drowsiness").
- **Inputs**: side_effects_en field per row
- **Outputs**: Validated non-empty strings
- **Edge cases**: Multiple side effects separated by commas

### FR-9: timing_instructions column — non-empty
- **What**: Every row must have `timing_instructions` describing when/how to take the medicine (e.g., "Take after meals", "Once daily at bedtime").
- **Inputs**: timing_instructions field per row
- **Outputs**: Validated non-empty strings
- **Edge cases**: Should be concise and patient-friendly

### FR-10: known_interactions column — may be empty
- **What**: The `known_interactions` column lists known drug interactions. This field MAY be empty (not all drugs have notable interactions for a patient-facing context).
- **Inputs**: known_interactions field per row
- **Outputs**: String (may be empty)
- **Edge cases**: When present, interactions separated by semicolons (e.g., "Avoid with alcohol; Do not take with blood thinners")

### FR-11: No duplicate brand names
- **What**: Each `brand_name` must be unique across the entire CSV (case-insensitive).
- **Inputs**: All brand_name values
- **Outputs**: Uniqueness check passes
- **Edge cases**: "Crocin" and "crocin" are considered duplicates

### FR-12: CSV parseable by Python csv module
- **What**: The file must be parseable by Python's `csv.DictReader` without errors.
- **Inputs**: File contents
- **Outputs**: All rows parsed successfully
- **Edge cases**: Fields with commas must be properly quoted; no unescaped special characters

---

## Tangible Outcomes

- [ ] **Outcome 1**: `data/drugs/medicines.csv` exists and is valid UTF-8
- [ ] **Outcome 2**: Header row has exactly 7 required columns in correct order
- [ ] **Outcome 3**: At least 50 medicine entries (non-empty rows)
- [ ] **Outcome 4**: All required fields (brand_name, generic_name, therapeutic_class, purpose_en, side_effects_en, timing_instructions) are non-empty in every row
- [ ] **Outcome 5**: known_interactions may be empty but column exists
- [ ] **Outcome 6**: No duplicate brand names (case-insensitive)
- [ ] **Outcome 7**: File is parseable by `csv.DictReader`
- [ ] **Outcome 8**: Data covers common Indian medicine categories (analgesics, antibiotics, antihypertensives, antidiabetics, antacids, etc.)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_csv_file_exists**: Assert `data/drugs/medicines.csv` exists on disk
2. **test_csv_utf8_encoding**: Assert file is valid UTF-8
3. **test_csv_header_columns**: Assert header row has exactly the 7 required columns
4. **test_csv_header_order**: Assert columns appear in the specified order
5. **test_csv_minimum_row_count**: Assert at least 50 data rows (excluding header)
6. **test_csv_brand_name_non_empty**: Assert every row has non-empty brand_name
7. **test_csv_brand_name_stripped**: Assert no leading/trailing whitespace in brand_name
8. **test_csv_generic_name_non_empty**: Assert every row has non-empty generic_name
9. **test_csv_therapeutic_class_non_empty**: Assert every row has non-empty therapeutic_class
10. **test_csv_purpose_en_non_empty**: Assert every row has non-empty purpose_en
11. **test_csv_purpose_en_max_length**: Assert purpose_en <= 200 characters per row
12. **test_csv_side_effects_non_empty**: Assert every row has non-empty side_effects_en
13. **test_csv_timing_instructions_non_empty**: Assert every row has non-empty timing_instructions
14. **test_csv_known_interactions_column_exists**: Assert column exists (values may be empty)
15. **test_csv_no_duplicate_brand_names**: Assert all brand_name values unique (case-insensitive)
16. **test_csv_parseable_by_dictreader**: Assert entire file parses without error via csv.DictReader
17. **test_csv_no_empty_rows**: Assert no rows where all fields are empty
18. **test_csv_covers_common_categories**: Assert at least 5 distinct therapeutic_class values
19. **test_csv_brand_name_no_duplicates_with_generic**: Assert brand_name != generic_name (they are different fields)
20. **test_csv_row_field_count**: Assert every row has exactly 7 fields (no missing/extra columns)

### Mocking Strategy
- No mocking needed — this is pure static file validation (same approach as S6.1 glossary data tests)

### Coverage Expectation
- All 7 columns validated for presence and constraints
- Data quality checks (uniqueness, length, categories)
- File format checks (UTF-8, parseable, no empty rows)

---

## References
- roadmap.md Phase 8 — Drug Lookup
- S8.2 (load_drug_csv) — consumer of this CSV
- S6.1 (glossary data files) — analogous data spec pattern
- design.md, requirements.md
