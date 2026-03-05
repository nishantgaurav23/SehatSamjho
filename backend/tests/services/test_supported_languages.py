"""Tests for S3.1 — Supported Languages.

Pure data + pure functions. No mocking needed.
"""

from backend.app.services.whatsapp import (
    SUPPORTED_LANGUAGES,
    TOP_LANGUAGES,
    get_language_name,
    is_supported_language,
)


# ---------------------------------------------------------------------------
# SUPPORTED_LANGUAGES tests
# ---------------------------------------------------------------------------


class TestSupportedLanguages:
    """Tests for the SUPPORTED_LANGUAGES dictionary."""

    def test_supported_languages_has_22_entries(self):
        assert len(SUPPORTED_LANGUAGES) == 22

    def test_supported_languages_keys_are_strings(self):
        for key in SUPPORTED_LANGUAGES:
            assert isinstance(key, str)
            assert len(key) > 0

    def test_supported_languages_values_have_required_keys(self):
        required = {"name", "display_name", "bhashini_code"}
        for code, value in SUPPORTED_LANGUAGES.items():
            assert required.issubset(value.keys()), (
                f"Language '{code}' missing keys: {required - set(value.keys())}"
            )

    def test_supported_languages_no_empty_values(self):
        for code, value in SUPPORTED_LANGUAGES.items():
            for field in ("name", "display_name", "bhashini_code"):
                assert isinstance(value[field], str), (
                    f"Language '{code}' field '{field}' is not a string"
                )
                assert len(value[field]) > 0, f"Language '{code}' field '{field}' is empty"

    def test_supported_languages_contains_hindi(self):
        assert "hi" in SUPPORTED_LANGUAGES
        assert SUPPORTED_LANGUAGES["hi"]["name"] == "Hindi"

    def test_supported_languages_contains_tamil(self):
        assert "ta" in SUPPORTED_LANGUAGES
        assert SUPPORTED_LANGUAGES["ta"]["name"] == "Tamil"

    def test_supported_languages_contains_all_top_8(self):
        top_8 = ["hi", "bn", "ta", "te", "mr", "gu", "kn", "ml"]
        for code in top_8:
            assert code in SUPPORTED_LANGUAGES, f"Top-8 code '{code}' not in SUPPORTED_LANGUAGES"

    def test_bhashini_codes_match_keys(self):
        for code, value in SUPPORTED_LANGUAGES.items():
            assert value["bhashini_code"] == code, (
                f"Language '{code}': bhashini_code '{value['bhashini_code']}' != key '{code}'"
            )

    def test_display_names_are_non_ascii(self):
        # All display names should contain non-ASCII characters (native script)
        for code, value in SUPPORTED_LANGUAGES.items():
            display = value["display_name"]
            has_non_ascii = any(ord(c) > 127 for c in display)
            assert has_non_ascii, (
                f"Language '{code}' display_name '{display}' has no non-ASCII characters"
            )


# ---------------------------------------------------------------------------
# TOP_LANGUAGES tests
# ---------------------------------------------------------------------------


class TestTopLanguages:
    """Tests for the TOP_LANGUAGES list."""

    def test_top_languages_has_8_entries(self):
        assert len(TOP_LANGUAGES) == 8

    def test_top_languages_all_in_supported(self):
        for code in TOP_LANGUAGES:
            assert code in SUPPORTED_LANGUAGES, (
                f"TOP_LANGUAGES code '{code}' not in SUPPORTED_LANGUAGES"
            )

    def test_top_languages_order(self):
        assert TOP_LANGUAGES[0] == "hi", "First language should be Hindi ('hi')"


# ---------------------------------------------------------------------------
# get_language_name() tests
# ---------------------------------------------------------------------------


class TestGetLanguageName:
    """Tests for the get_language_name helper."""

    def test_get_language_name_valid_code(self):
        assert get_language_name("hi") == "Hindi"

    def test_get_language_name_invalid_code(self):
        assert get_language_name("xyz") is None

    def test_get_language_name_empty_string(self):
        assert get_language_name("") is None

    def test_get_language_name_case_insensitive(self):
        assert get_language_name("HI") == "Hindi"


# ---------------------------------------------------------------------------
# is_supported_language() tests
# ---------------------------------------------------------------------------


class TestIsSupportedLanguage:
    """Tests for the is_supported_language helper."""

    def test_is_supported_language_valid(self):
        assert is_supported_language("ta") is True

    def test_is_supported_language_invalid(self):
        assert is_supported_language("xx") is False

    def test_is_supported_language_empty(self):
        assert is_supported_language("") is False

    def test_is_supported_language_case_insensitive(self):
        assert is_supported_language("TA") is True
