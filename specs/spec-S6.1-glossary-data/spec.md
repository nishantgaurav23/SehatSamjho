# Spec S6.1 — Glossary Data Files

## Overview
Curated per-language JSON files mapping medical terms to plain-language explanations and vernacular translations. These files serve as the grounding data for the glossary RAG system that injects context into the Claude translation prompt. Top 6 languages by usage: Hindi (hi), Tamil (ta), Telugu (te), Kannada (kn), Bengali (bn), Marathi (mr). Each file contains ~100 entries for the prototype. Each entry has three fields: `term` (English medical term), `explanation` (plain-English description), and `vernacular` (translation in the target language). The JSON schema aligns with the existing `GlossaryEntry` Pydantic model defined in S2.4.

## Dependencies
- None (standalone data files; however, the `GlossaryEntry` schema from S2.4 defines the contract each JSON entry must satisfy)

## Target Location
- `data/glossary/hi.json` — Hindi
- `data/glossary/ta.json` — Tamil
- `data/glossary/te.json` — Telugu
- `data/glossary/kn.json` — Kannada
- `data/glossary/bn.json` — Bengali
- `data/glossary/mr.json` — Marathi

---

## Functional Requirements

### FR-1: JSON File Structure
- **What**: Each glossary file is a valid JSON array of objects. Every object has exactly three string fields: `term`, `explanation`, `vernacular`.
- **Inputs**: Static file on disk at `data/glossary/{lang_code}.json`
- **Outputs**: Parseable JSON array
- **Edge cases**: No empty strings for any field. No duplicate `term` values within a single file. All files must be valid JSON (no trailing commas, no comments).

### FR-2: Entry Schema Conformance
- **What**: Every entry in every glossary file must be deserializable into the `GlossaryEntry` Pydantic model (term: str min_length=1, explanation: str min_length=1, vernacular: str min_length=1).
- **Inputs**: Each JSON object from each file
- **Outputs**: Valid `GlossaryEntry` instance
- **Edge cases**: Whitespace-only strings should not appear. Unicode characters in vernacular field are expected and valid.

### FR-3: Language Coverage
- **What**: Exactly 6 glossary files must exist, one per target language: hi, ta, te, kn, bn, mr.
- **Inputs**: Directory listing of `data/glossary/`
- **Outputs**: 6 files matching the expected language codes
- **Edge cases**: No extra files, no missing files. File names must be lowercase language codes with `.json` extension.

### FR-4: Medical Term Coverage
- **What**: Each file contains at least 20 entries (prototype minimum) covering common medical terms found in Indian prescriptions: conditions (hypertension, diabetes, fever), medication instructions (twice daily, before meals), body parts, and common lab terms.
- **Inputs**: File content
- **Outputs**: Array length >= 20
- **Edge cases**: Terms should be lowercase English for consistent matching. Explanations should be patient-friendly (no jargon restating jargon).

### FR-5: Term Uniqueness
- **What**: Within each language file, no two entries may share the same `term` value (case-insensitive).
- **Inputs**: All entries in a single file
- **Outputs**: No duplicates
- **Edge cases**: "Hypertension" and "hypertension" count as duplicates.

### FR-6: Consistent Term Set Across Languages
- **What**: All 6 language files should share the same set of `term` values (English medical terms). The `explanation` field may be identical across languages (it's in English), but `vernacular` must differ per language.
- **Inputs**: Term sets from all 6 files
- **Outputs**: Identical term sets
- **Edge cases**: Order of entries within files may differ.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `data/glossary/` directory exists with exactly 6 JSON files: hi.json, ta.json, te.json, kn.json, bn.json, mr.json
- [ ] **Outcome 2**: Every file is valid JSON and parses as a list of objects
- [ ] **Outcome 3**: Every entry in every file validates against the `GlossaryEntry` Pydantic model
- [ ] **Outcome 4**: Each file has at least 20 entries
- [ ] **Outcome 5**: No duplicate terms within any single file (case-insensitive)
- [ ] **Outcome 6**: All 6 files share the same set of English terms
- [ ] **Outcome 7**: Vernacular values contain non-ASCII characters appropriate to each language's script

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_glossary_directory_exists**: `data/glossary/` directory exists
2. **test_all_six_files_present**: Exactly hi.json, ta.json, te.json, kn.json, bn.json, mr.json exist
3. **test_no_extra_files**: No unexpected files in the glossary directory
4. **test_valid_json_{lang}** (x6): Each file parses as valid JSON
5. **test_is_list_{lang}** (x6): Parsed JSON is a list (not dict or scalar)
6. **test_entry_schema_{lang}** (x6): Every entry validates as `GlossaryEntry`
7. **test_minimum_entries_{lang}** (x6): Each file has >= 20 entries
8. **test_no_duplicate_terms_{lang}** (x6): No duplicate terms within file (case-insensitive)
9. **test_terms_consistent_across_languages**: All 6 files share the same term set
10. **test_vernacular_non_ascii_{lang}** (x6): Vernacular field contains non-ASCII chars (Devanagari, Tamil, Telugu, Kannada, Bengali scripts)
11. **test_term_lowercase_{lang}** (x6): All terms are lowercase
12. **test_explanation_not_empty_{lang}** (x6): No empty or whitespace-only explanations
13. **test_vernacular_differs_per_language**: For a sample term, vernacular values are different across all 6 files

### Mocking Strategy
- No mocking needed — these are pure static file validation tests

### Coverage Expectation
- All 6 files validated for structure, schema, uniqueness, and cross-language consistency
- ~20 tests total (parameterized across languages where applicable)

---

## References
- roadmap.md — Phase 6: Medical Glossary
- `backend/app/models/schemas.py` — `GlossaryEntry` model (S2.4)
- S6.2 (GlossaryLoader) will consume these files
- S11.6 (Glossary data files) is the infra/seeding counterpart
