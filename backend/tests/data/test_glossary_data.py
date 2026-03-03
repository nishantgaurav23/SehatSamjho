"""S6.1 — Glossary Data Files: static file validation tests.

Pure file-system tests — no mocking needed.
Validates structure, schema conformance, uniqueness, and cross-language
consistency of the curated glossary JSON files.
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
MIN_ENTRIES = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_glossary(lang_code: str) -> list[dict]:
    """Load and parse a single glossary file."""
    path = GLOSSARY_DIR / f"{lang_code}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Phase 1: Directory & file presence (3 tests)
# ---------------------------------------------------------------------------


class TestDirectoryAndFiles:
    """Glossary directory structure."""

    def test_glossary_directory_exists(self):
        assert GLOSSARY_DIR.is_dir(), f"{GLOSSARY_DIR} must exist"

    def test_all_six_files_present(self):
        actual = {p.stem for p in GLOSSARY_DIR.glob("*.json")}
        assert EXPECTED_LANG_CODES == actual

    def test_no_extra_files(self):
        non_json = [
            p.name for p in GLOSSARY_DIR.iterdir() if p.suffix != ".json" and p.name != ".gitkeep"
        ]
        assert non_json == [], f"Unexpected files: {non_json}"


# ---------------------------------------------------------------------------
# Phase 2: JSON validity (parameterized x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestJsonValidity:
    """Each file is valid JSON containing a list."""

    def test_valid_json(self, lang: str):
        data = _load_glossary(lang)
        assert isinstance(data, list)

    def test_is_list(self, lang: str):
        data = _load_glossary(lang)
        assert isinstance(data, list), "Top-level JSON must be a list"


# ---------------------------------------------------------------------------
# Phase 3: Schema conformance (parameterized x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestSchemaConformance:
    """Every entry validates against GlossaryEntry."""

    def test_entry_schema(self, lang: str):
        data = _load_glossary(lang)
        for i, entry in enumerate(data):
            try:
                GlossaryEntry(**entry)
            except Exception as exc:
                pytest.fail(f"{lang}.json entry #{i} invalid: {exc}")


# ---------------------------------------------------------------------------
# Phase 4: Minimum entry count (parameterized x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestMinimumEntries:
    """Each file has >= 20 entries."""

    def test_minimum_entries(self, lang: str):
        data = _load_glossary(lang)
        assert (
            len(data) >= MIN_ENTRIES
        ), f"{lang}.json has {len(data)} entries, need >= {MIN_ENTRIES}"


# ---------------------------------------------------------------------------
# Phase 5: Term uniqueness (parameterized x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestTermUniqueness:
    """No duplicate terms within a single file (case-insensitive)."""

    def test_no_duplicate_terms(self, lang: str):
        data = _load_glossary(lang)
        terms = [e["term"].lower() for e in data]
        dupes = [t for t in terms if terms.count(t) > 1]
        assert dupes == [], f"Duplicate terms in {lang}.json: {set(dupes)}"


# ---------------------------------------------------------------------------
# Phase 6: Cross-language consistency (1 test)
# ---------------------------------------------------------------------------


class TestCrossLanguage:
    """All 6 files share the same term set."""

    def test_terms_consistent_across_languages(self):
        term_sets: dict[str, set[str]] = {}
        for lang in sorted(EXPECTED_LANG_CODES):
            data = _load_glossary(lang)
            term_sets[lang] = {e["term"].lower() for e in data}

        reference = term_sets["hi"]
        for lang, terms in term_sets.items():
            assert terms == reference, (
                f"{lang} term set differs from hi: "
                f"missing={reference - terms}, extra={terms - reference}"
            )

    def test_vernacular_differs_per_language(self):
        """For the first term in hi.json, vernacular should differ across all 6."""
        hi_data = _load_glossary("hi")
        sample_term = hi_data[0]["term"]

        vernaculars: dict[str, str] = {}
        for lang in sorted(EXPECTED_LANG_CODES):
            data = _load_glossary(lang)
            match = [e for e in data if e["term"] == sample_term]
            assert match, f"{lang}.json missing term '{sample_term}'"
            vernaculars[lang] = match[0]["vernacular"]

        unique_vernaculars = set(vernaculars.values())
        assert len(unique_vernaculars) == len(
            EXPECTED_LANG_CODES
        ), f"Vernacular should differ per language: {vernaculars}"


# ---------------------------------------------------------------------------
# Phase 7: Vernacular non-ASCII (parameterized x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestVernacularNonAscii:
    """Vernacular fields contain non-ASCII chars (Indic scripts)."""

    def test_vernacular_non_ascii(self, lang: str):
        data = _load_glossary(lang)
        for i, entry in enumerate(data):
            v = entry["vernacular"]
            assert any(
                ord(c) > 127 for c in v
            ), f"{lang}.json entry #{i} vernacular is pure ASCII: '{v}'"


# ---------------------------------------------------------------------------
# Phase 8: Term lowercase (parameterized x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestTermLowercase:
    """All terms are lowercase English."""

    def test_term_lowercase(self, lang: str):
        data = _load_glossary(lang)
        for i, entry in enumerate(data):
            assert (
                entry["term"] == entry["term"].lower()
            ), f"{lang}.json entry #{i} term not lowercase: '{entry['term']}'"


# ---------------------------------------------------------------------------
# Phase 9: Explanation non-empty (parameterized x6)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", sorted(EXPECTED_LANG_CODES))
class TestExplanationNonEmpty:
    """No empty or whitespace-only explanations."""

    def test_explanation_not_empty(self, lang: str):
        data = _load_glossary(lang)
        for i, entry in enumerate(data):
            assert entry["explanation"].strip(), f"{lang}.json entry #{i} has empty explanation"
