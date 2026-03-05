"""S11.6 — Glossary Data Files (expanded): validation tests.

Pure file-system tests — no mocking needed.
Validates that each of the 6 glossary JSON files has been expanded to >= 100
entries with proper data quality, cross-language consistency, medical category
coverage, and backward compatibility with S6.1 original entries.
"""

import json
from pathlib import Path

import pytest

from backend.app.models.schemas import GlossaryEntry

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GLOSSARY_DIR = Path(__file__).resolve().parents[3] / "data" / "glossary"
EXPECTED_LANG_CODES = {"hi", "ta", "te", "kn", "bn", "mr"}
MIN_ENTRIES = 100

# Original S6.1 terms that must be preserved
ORIGINAL_S61_TERMS = [
    "hypertension",
    "diabetes",
    "fever",
    "tablet",
    "antibiotic",
    "insulin",
    "blood pressure",
    "cholesterol",
    "asthma",
    "infection",
]

# Medical categories and representative terms for FR-7
MEDICAL_CATEGORIES = {
    "conditions": ["hypertension", "diabetes", "asthma", "anemia"],
    "medication_instructions": ["twice daily", "before meals", "after meals", "once daily"],
    "body_parts": ["liver", "kidney", "heart", "lung"],
    "lab_terms": ["blood sugar", "cholesterol", "hemoglobin", "creatinine"],
    "procedures": ["x-ray", "ultrasound", "ecg", "blood test"],
    "symptoms": ["fever", "nausea", "headache", "dizziness"],
    "drug_classes": ["antibiotic", "analgesic", "antacid", "antifungal"],
    "dosage_forms": ["tablet", "capsule", "syrup", "injection"],
    "abbreviations": ["bp", "od", "bd", "sos"],
    "general_medical": ["diagnosis", "prescription", "dosage", "side effect"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_glossary(lang_code: str) -> list[dict]:
    """Load and parse a single glossary file."""
    path = GLOSSARY_DIR / f"{lang_code}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _get_all_terms(lang_code: str) -> set[str]:
    """Get lowercase term set for a language."""
    data = _load_glossary(lang_code)
    return {e["term"].lower() for e in data}


# ---------------------------------------------------------------------------
# Test 1: Directory exists
# ---------------------------------------------------------------------------


class TestGlossaryDirectoryExists:
    def test_glossary_directory_exists(self):
        """FR-10: data/glossary/ directory exists."""
        assert GLOSSARY_DIR.is_dir(), f"{GLOSSARY_DIR} must exist"


# ---------------------------------------------------------------------------
# Test 2: All 6 files present
# ---------------------------------------------------------------------------


class TestAllSixFilesPresent:
    def test_all_six_files_present(self):
        """FR-10: Exactly hi, ta, te, kn, bn, mr JSON files exist."""
        actual = {p.stem for p in GLOSSARY_DIR.glob("*.json")}
        assert EXPECTED_LANG_CODES == actual


# ---------------------------------------------------------------------------
# Test 3: Valid JSON (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestValidJson:
    def test_valid_json(self, lang: str):
        """FR-10: Each file parses as valid JSON without errors."""
        data = _load_glossary(lang)
        assert isinstance(data, list)


# ---------------------------------------------------------------------------
# Test 4: Is list (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestIsList:
    def test_is_list(self, lang: str):
        """FR-10: Parsed JSON is a list."""
        data = _load_glossary(lang)
        assert isinstance(data, list), "Top-level JSON must be a list"


# ---------------------------------------------------------------------------
# Test 5: At least 100 entries (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestAtLeast100Entries:
    def test_at_least_100_entries(self, lang: str):
        """FR-1: Each file has >= 100 entries."""
        data = _load_glossary(lang)
        assert len(data) >= MIN_ENTRIES, (
            f"{lang}.json has {len(data)} entries, need >= {MIN_ENTRIES}"
        )


# ---------------------------------------------------------------------------
# Test 6: Entry schema (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestEntrySchema:
    def test_entry_schema(self, lang: str):
        """FR-2: Every entry validates as GlossaryEntry Pydantic model."""
        data = _load_glossary(lang)
        for i, entry in enumerate(data):
            try:
                GlossaryEntry(**entry)
            except Exception as exc:
                pytest.fail(f"{lang}.json entry #{i} invalid: {exc}")


# ---------------------------------------------------------------------------
# Test 7: All fields non-empty (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestAllFieldsNonEmpty:
    def test_all_fields_non_empty(self, lang: str):
        """FR-2: No empty or whitespace-only values in any field."""
        data = _load_glossary(lang)
        for i, entry in enumerate(data):
            assert entry["term"].strip(), f"{lang}.json entry #{i} has empty term"
            assert entry["explanation"].strip(), f"{lang}.json entry #{i} has empty explanation"
            assert entry["vernacular"].strip(), f"{lang}.json entry #{i} has empty vernacular"


# ---------------------------------------------------------------------------
# Test 8: No duplicate terms (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestNoDuplicateTerms:
    def test_no_duplicate_terms(self, lang: str):
        """FR-4: No duplicate terms within file (case-insensitive)."""
        data = _load_glossary(lang)
        seen: dict[str, int] = {}
        for i, entry in enumerate(data):
            key = entry["term"].lower()
            assert key not in seen, (
                f"Duplicate term '{entry['term']}' in {lang}.json at entries {seen[key]} and {i}"
            )
            seen[key] = i


# ---------------------------------------------------------------------------
# Test 9: Terms consistent across languages
# ---------------------------------------------------------------------------


class TestTermsConsistentAcrossLanguages:
    def test_terms_consistent_across_languages(self):
        """FR-5: All 6 files share the same term set."""
        term_sets: dict[str, set[str]] = {}
        for lang in sorted(EXPECTED_LANG_CODES):
            term_sets[lang] = _get_all_terms(lang)

        reference = term_sets["hi"]
        for lang, terms in term_sets.items():
            assert terms == reference, (
                f"{lang} term set differs from hi: "
                f"missing={reference - terms}, extra={terms - reference}"
            )


# ---------------------------------------------------------------------------
# Test 10: Terms all lowercase (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestTermsAllLowercase:
    def test_terms_all_lowercase(self, lang: str):
        """FR-6: All terms equal their lowercase form."""
        data = _load_glossary(lang)
        for i, entry in enumerate(data):
            assert entry["term"] == entry["term"].lower(), (
                f"{lang}.json entry #{i} term not lowercase: '{entry['term']}'"
            )


# ---------------------------------------------------------------------------
# Test 11: Vernacular non-ASCII (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestVernacularNonAscii:
    def test_vernacular_non_ascii(self, lang: str):
        """FR-8: Vernacular field contains non-ASCII chars."""
        data = _load_glossary(lang)
        for i, entry in enumerate(data):
            v = entry["vernacular"]
            assert any(ord(c) > 127 for c in v), (
                f"{lang}.json entry #{i} vernacular is pure ASCII: '{v}'"
            )


# ---------------------------------------------------------------------------
# Test 12: Vernacular differs per language
# ---------------------------------------------------------------------------


class TestVernacularDiffersPerLanguage:
    def test_vernacular_differs_per_language(self):
        """FR-8: For a sample term, vernacular values differ across all 6."""
        hi_data = _load_glossary("hi")
        sample_term = hi_data[0]["term"]

        vernaculars: dict[str, str] = {}
        for lang in sorted(EXPECTED_LANG_CODES):
            data = _load_glossary(lang)
            match = [e for e in data if e["term"] == sample_term]
            assert match, f"{lang}.json missing term '{sample_term}'"
            vernaculars[lang] = match[0]["vernacular"]

        unique_vernaculars = set(vernaculars.values())
        assert len(unique_vernaculars) == len(EXPECTED_LANG_CODES), (
            f"Vernacular should differ per language: {vernaculars}"
        )


# ---------------------------------------------------------------------------
# Test 13: Explanation max length (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestExplanationMaxLength:
    def test_explanation_max_length(self, lang: str):
        """FR-9: All explanation values <= 200 characters."""
        data = _load_glossary(lang)
        for i, entry in enumerate(data):
            length = len(entry["explanation"])
            assert length <= 200, f"{lang}.json entry #{i} explanation is {length} chars, max 200"


# ---------------------------------------------------------------------------
# Test 14: Original entries preserved (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestOriginalEntriesPreserved:
    def test_original_entries_preserved(self, lang: str):
        """FR-3: Key S6.1 terms must still be present."""
        terms = _get_all_terms(lang)
        for expected in ORIGINAL_S61_TERMS:
            assert expected in terms, f"Original S6.1 term '{expected}' not found in {lang}.json"


# ---------------------------------------------------------------------------
# Test 15: No BOM marker (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestNoBomMarker:
    def test_no_bom_marker(self, lang: str):
        """FR-10: Files do not start with UTF-8 BOM."""
        path = GLOSSARY_DIR / f"{lang}.json"
        raw = path.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{lang}.json has UTF-8 BOM marker"


# ---------------------------------------------------------------------------
# Test 16: Valid UTF-8 (x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestValidUtf8:
    def test_valid_utf8(self, lang: str):
        """FR-10: Files decode as UTF-8 without errors."""
        path = GLOSSARY_DIR / f"{lang}.json"
        path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 17: Medical category coverage
# ---------------------------------------------------------------------------


class TestMedicalCategoryCoverage:
    def test_medical_category_coverage(self):
        """FR-7: Terms span at least 10 medical categories."""
        terms = _get_all_terms("hi")
        covered_categories = 0
        for category, representative_terms in MEDICAL_CATEGORIES.items():
            if any(t in terms for t in representative_terms):
                covered_categories += 1

        assert covered_categories >= 10, (
            f"Only {covered_categories} medical categories covered, need >= 10"
        )


# ---------------------------------------------------------------------------
# Test 18: Explanation not circular
# ---------------------------------------------------------------------------


class TestExplanationNotCircular:
    def test_explanation_not_circular(self):
        """FR-9: Spot-check that explanations don't simply restate the term."""
        data = _load_glossary("hi")
        for entry in data:
            term = entry["term"].lower()
            explanation = entry["explanation"].lower()
            # Explanation should not start with the exact term
            assert not explanation.startswith(f"{term} is {term}"), (
                f"Circular explanation for '{term}': '{entry['explanation']}'"
            )
            # Explanation should be longer than the term itself
            assert len(entry["explanation"]) > len(entry["term"]) + 5, (
                f"Explanation too short for '{term}': '{entry['explanation']}'"
            )


# ---------------------------------------------------------------------------
# Test 19: No extra files
# ---------------------------------------------------------------------------


class TestNoExtraFiles:
    def test_no_extra_files(self):
        """FR-10: No unexpected files in the glossary directory."""
        non_json = [
            p.name for p in GLOSSARY_DIR.iterdir() if p.suffix != ".json" and p.name != ".gitkeep"
        ]
        assert non_json == [], f"Unexpected files: {non_json}"


# ---------------------------------------------------------------------------
# Test 20: Entry count consistent across languages
# ---------------------------------------------------------------------------


class TestEntryCountConsistent:
    def test_entry_count_consistent_across_languages(self):
        """FR-5: All 6 files have the same number of entries."""
        counts: dict[str, int] = {}
        for lang in sorted(EXPECTED_LANG_CODES):
            data = _load_glossary(lang)
            counts[lang] = len(data)

        unique_counts = set(counts.values())
        assert len(unique_counts) == 1, f"Entry counts differ across languages: {counts}"
