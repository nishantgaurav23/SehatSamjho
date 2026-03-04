# Spec S11.6 — Glossary Data Files (Data Files)

## Overview
Expand the curated per-language glossary JSON files from ~25 entries (created in S6.1) to ~100 entries each for the prototype. The files use the same 3-field schema established in S6.1 (`term`, `explanation`, `vernacular`). Files cover 6 languages: Hindi (hi), Tamil (ta), Telugu (te), Kannada (kn), Bengali (bn), Marathi (mr). Each entry maps an English medical term to a plain-language explanation and a vernacular translation in the target language's script. These files are loaded into Redis at startup via `make seed` (S11.7) and queried by `lookup_terms()` (S6.3) to inject grounding context into the Claude translation prompt.

## Dependencies
- **S6.1** (Glossary data files schema) — defines JSON structure, validation rules, and initial 25-entry dataset per language

## Target Location
- `data/glossary/hi.json` — Hindi
- `data/glossary/ta.json` — Tamil
- `data/glossary/te.json` — Telugu
- `data/glossary/kn.json` — Kannada
- `data/glossary/bn.json` — Bengali
- `data/glossary/mr.json` — Marathi

---

## Functional Requirements

### FR-1: Each file contains at least 100 entries
- **What**: Each glossary JSON file must contain at least 100 entries (expanded from S6.1's 25), covering the breadth of medical terms commonly found in Indian prescriptions
- **Inputs**: Static JSON file on disk
- **Outputs**: JSON array with >= 100 objects
- **Edge cases**: No empty arrays; each entry must have all 3 fields populated

### FR-2: All 3 fields populated for every entry
- **What**: Every entry must have non-empty values for: `term`, `explanation`, `vernacular`. No whitespace-only strings
- **Inputs**: JSON entry objects
- **Outputs**: All fields are non-empty after stripping whitespace
- **Edge cases**: Unicode characters in `vernacular` are expected and valid; `term` should be plain ASCII English

### FR-3: Original S6.1 entries preserved
- **What**: All 25 entries from the S6.1 glossary files must remain in the expanded dataset (backward compatibility). No data should be lost or altered from the original prototype entries
- **Inputs**: Original 25 terms from S6.1
- **Outputs**: All 25 present in expanded files
- **Edge cases**: If corrections to original data are needed, document them

### FR-4: Terms are unique within each file (case-insensitive)
- **What**: No two entries in the same file share the same `term` value when compared case-insensitively
- **Inputs**: All entries in a single file
- **Outputs**: Zero duplicates
- **Edge cases**: "Hypertension" and "hypertension" count as duplicates

### FR-5: Consistent term set across all 6 languages
- **What**: All 6 language files must share the exact same set of `term` values (English medical terms). The `explanation` field may be identical across languages, but `vernacular` must differ per language
- **Inputs**: Term sets from all 6 files
- **Outputs**: Identical term sets across all files
- **Edge cases**: Order of entries within files may differ

### FR-6: Terms are all lowercase
- **What**: All `term` values must be lowercase English for consistent matching by `lookup_terms()` which normalizes to lowercase
- **Inputs**: `term` field of every entry
- **Outputs**: All terms match `term == term.lower()`
- **Edge cases**: Terms like "ECG" should be stored as "ecg"

### FR-7: Broad medical category coverage
- **What**: The expanded dataset must cover at least 10 medical categories: conditions (hypertension, diabetes), medication instructions (twice daily, before meals), body parts (liver, kidney), lab terms (blood sugar, cholesterol), procedures (x-ray, ultrasound), symptoms (fever, nausea), drug classes (antibiotic, analgesic), dosage forms (tablet, syrup), and common abbreviations (BP, OD)
- **Inputs**: Terms in the dataset
- **Outputs**: Coverage across categories
- **Edge cases**: Some terms may span multiple categories

### FR-8: Vernacular contains appropriate script characters
- **What**: The `vernacular` field for each language must contain characters from the appropriate script: Devanagari (hi, mr), Tamil (ta), Telugu (te), Kannada (kn), Bengali (bn)
- **Inputs**: `vernacular` field per language
- **Outputs**: Non-ASCII characters present, matching the language's script
- **Edge cases**: Some vernacular entries may also include English words (drug names) alongside native script

### FR-9: Explanation is patient-friendly
- **What**: The `explanation` field must be written in plain English that a patient can understand. Each explanation should be <= 200 characters
- **Inputs**: `explanation` field
- **Outputs**: Clear, concise plain-language descriptions
- **Edge cases**: Avoid circular definitions (don't define "analgesic" as "an analgesic drug")

### FR-10: Valid JSON files
- **What**: All files must be valid UTF-8 JSON, parseable by Python's `json.load()` without errors. No BOM markers, no trailing commas, no comments
- **Inputs**: Raw file
- **Outputs**: Successfully parsed JSON
- **Edge cases**: Files with Unicode must be properly encoded as UTF-8

---

## Tangible Outcomes

- [ ] **Outcome 1**: Each of the 6 glossary files (hi, ta, te, kn, bn, mr) contains >= 100 entries
- [ ] **Outcome 2**: All entries have non-empty `term`, `explanation`, and `vernacular` fields
- [ ] **Outcome 3**: Original 25 S6.1 entries are present and intact in each file
- [ ] **Outcome 4**: No duplicate terms within any single file (case-insensitive)
- [ ] **Outcome 5**: All 6 files share the same set of English terms
- [ ] **Outcome 6**: All terms are lowercase
- [ ] **Outcome 7**: Vernacular values contain non-ASCII characters appropriate to each language's script
- [ ] **Outcome 8**: All explanation values are <= 200 characters
- [ ] **Outcome 9**: All files are valid UTF-8 JSON parseable by `json.load()`
- [ ] **Outcome 10**: Existing S6.1 tests (`backend/tests/data/test_glossary_data.py`) still pass

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_glossary_directory_exists**: `data/glossary/` directory exists
2. **test_all_six_files_present**: Exactly hi.json, ta.json, te.json, kn.json, bn.json, mr.json exist
3. **test_valid_json_{lang}** (x6): Each file parses as valid JSON without errors
4. **test_is_list_{lang}** (x6): Parsed JSON is a list (not dict or scalar)
5. **test_at_least_100_entries_{lang}** (x6): Each file has >= 100 entries (upgraded from S6.1's 20)
6. **test_entry_schema_{lang}** (x6): Every entry validates as `GlossaryEntry` Pydantic model
7. **test_all_fields_non_empty_{lang}** (x6): No empty or whitespace-only values in any field
8. **test_no_duplicate_terms_{lang}** (x6): No duplicate terms within file (case-insensitive)
9. **test_terms_consistent_across_languages**: All 6 files share the same term set
10. **test_terms_all_lowercase_{lang}** (x6): All terms equal their lowercase form
11. **test_vernacular_non_ascii_{lang}** (x6): Vernacular field contains non-ASCII chars
12. **test_vernacular_differs_per_language**: For a sample term, vernacular values are different across all 6 files
13. **test_explanation_max_length_{lang}** (x6): All explanation values <= 200 characters
14. **test_original_entries_preserved_{lang}** (x6): Spot-check that key S6.1 terms (hypertension, diabetes, fever, tablet, antibiotic) are present
15. **test_no_bom_marker_{lang}** (x6): Files do not start with UTF-8 BOM
16. **test_valid_utf8_{lang}** (x6): Files decode as UTF-8 without errors
17. **test_medical_category_coverage**: Terms span at least 10 medical categories (conditions, instructions, body parts, lab terms, etc.)
18. **test_explanation_not_circular**: Spot-check that explanations don't simply restate the term
19. **test_no_extra_files**: No unexpected files in the glossary directory
20. **test_entry_count_consistent_across_languages**: All 6 files have the same number of entries

### Mocking Strategy
- No mocking needed — these are pure static file validation tests (same pattern as S6.1 and S11.5)

### Coverage Expectation
- All 6 files validated for structure, schema, uniqueness, cross-language consistency, and data quality
- ~20 tests (parameterized across languages where applicable)
- Existing S6.1 tests must continue to pass (they test a subset of what S11.6 validates)

---

## References
- `roadmap.md` — Phase 11: Infra & Seeding
- `specs/spec-S6.1-glossary-data/` — original JSON schema and initial 25-entry dataset
- `backend/tests/data/test_glossary_data.py` — existing S6.1 validation tests (53 tests)
- `backend/app/services/glossary.py` — consumer of these files (GlossaryLoader, lookup_terms)
- `backend/app/models/schemas.py` — `GlossaryEntry` Pydantic model (S2.4)
