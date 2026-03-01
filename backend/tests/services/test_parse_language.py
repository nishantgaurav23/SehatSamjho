"""Tests for S3.2 — Parse Language Selection.

Pure function tests. No mocking needed.
"""

import pytest

from backend.app.services.whatsapp import (
    SUPPORTED_LANGUAGES,
    TOP_LANGUAGES,
    parse_language_selection,
)


# ---------------------------------------------------------------------------
# test_parse_numeric_valid — numbers 1–8 map to TOP_LANGUAGES
# ---------------------------------------------------------------------------


class TestParseNumericValid:
    """Each number 1–8 maps to the corresponding TOP_LANGUAGES entry."""

    @pytest.mark.parametrize(
        "number, expected_code",
        [(str(i), TOP_LANGUAGES[i - 1]) for i in range(1, 9)],
    )
    def test_parse_numeric_1_to_8(self, number, expected_code):
        result = parse_language_selection(number)
        assert result is not None
        name, code = result
        assert code == expected_code
        assert name == SUPPORTED_LANGUAGES[expected_code]["name"]

    def test_parse_numeric_1_is_hindi(self):
        assert parse_language_selection("1") == ("Hindi", "hi")

    def test_parse_numeric_3_is_tamil(self):
        assert parse_language_selection("3") == ("Tamil", "ta")

    def test_parse_numeric_8_is_malayalam(self):
        assert parse_language_selection("8") == ("Malayalam", "ml")


# ---------------------------------------------------------------------------
# test_parse_numeric_out_of_range — "0", "9", "99", "-1" return None
# ---------------------------------------------------------------------------


class TestParseNumericOutOfRange:
    """Out-of-range numeric inputs return None."""

    @pytest.mark.parametrize("value", ["0", "9", "99", "-1", "100", "10"])
    def test_out_of_range_returns_none(self, value):
        assert parse_language_selection(value) is None


# ---------------------------------------------------------------------------
# test_parse_language_code_valid — all 22 codes return (name, code)
# ---------------------------------------------------------------------------


class TestParseLanguageCodeValid:
    """All 22 language codes return correct (name, code) tuple."""

    @pytest.mark.parametrize("code", list(SUPPORTED_LANGUAGES.keys()))
    def test_all_22_codes(self, code):
        result = parse_language_selection(code)
        assert result is not None
        name, returned_code = result
        assert returned_code == code
        assert name == SUPPORTED_LANGUAGES[code]["name"]


# ---------------------------------------------------------------------------
# test_parse_language_code_case_insensitive — "HI", "Ta", "KOK" match
# ---------------------------------------------------------------------------


class TestParseLanguageCodeCaseInsensitive:
    """Language code matching is case-insensitive."""

    @pytest.mark.parametrize(
        "input_code, expected_code",
        [("HI", "hi"), ("Ta", "ta"), ("KOK", "kok"), ("BN", "bn"), ("Mr", "mr")],
    )
    def test_case_insensitive_codes(self, input_code, expected_code):
        result = parse_language_selection(input_code)
        assert result is not None
        name, code = result
        assert code == expected_code
        assert name == SUPPORTED_LANGUAGES[expected_code]["name"]


# ---------------------------------------------------------------------------
# test_parse_language_name_english — "Hindi", "tamil", "BENGALI" match
# ---------------------------------------------------------------------------


class TestParseLanguageNameEnglish:
    """English language names match correctly (case-insensitive)."""

    @pytest.mark.parametrize(
        "name_input, expected_code",
        [
            ("Hindi", "hi"),
            ("tamil", "ta"),
            ("BENGALI", "bn"),
            ("Telugu", "te"),
            ("marathi", "mr"),
            ("Gujarati", "gu"),
            ("Kannada", "kn"),
            ("Malayalam", "ml"),
            ("Odia", "or"),
            ("Punjabi", "pa"),
            ("Konkani", "kok"),
        ],
    )
    def test_english_name_match(self, name_input, expected_code):
        result = parse_language_selection(name_input)
        assert result is not None
        name, code = result
        assert code == expected_code
        assert name == SUPPORTED_LANGUAGES[expected_code]["name"]


# ---------------------------------------------------------------------------
# test_parse_language_name_display — native display_name matches
# ---------------------------------------------------------------------------


class TestParseLanguageNameDisplay:
    """Native script display_name matches correctly."""

    @pytest.mark.parametrize(
        "display, expected_code",
        [
            ("हिन्दी", "hi"),
            ("বাংলা", "bn"),
            ("தமிழ்", "ta"),
            ("తెలుగు", "te"),
            ("मराठी", "mr"),
            ("ગુજરાતી", "gu"),
            ("ಕನ್ನಡ", "kn"),
            ("മലയാളം", "ml"),
        ],
    )
    def test_display_name_match(self, display, expected_code):
        result = parse_language_selection(display)
        assert result is not None
        name, code = result
        assert code == expected_code
        assert name == SUPPORTED_LANGUAGES[expected_code]["name"]


# ---------------------------------------------------------------------------
# test_parse_whitespace_stripping — "  hi  ", " 1 " work
# ---------------------------------------------------------------------------


class TestParseWhitespaceStripping:
    """Leading/trailing whitespace is stripped before matching."""

    @pytest.mark.parametrize(
        "raw_input, expected",
        [
            ("  hi  ", ("Hindi", "hi")),
            (" 1 ", ("Hindi", "hi")),
            ("  Tamil  ", ("Tamil", "ta")),
            ("\tbn\n", ("Bengali", "bn")),
            ("  3  ", ("Tamil", "ta")),
        ],
    )
    def test_whitespace_stripped(self, raw_input, expected):
        assert parse_language_selection(raw_input) == expected


# ---------------------------------------------------------------------------
# test_parse_empty_string — "" returns None
# ---------------------------------------------------------------------------


class TestParseEmptyString:
    """Empty string returns None."""

    def test_empty_string(self):
        assert parse_language_selection("") is None


# ---------------------------------------------------------------------------
# test_parse_none_like — whitespace-only returns None
# ---------------------------------------------------------------------------


class TestParseNoneLike:
    """Whitespace-only inputs return None."""

    @pytest.mark.parametrize("value", [" ", "  ", "\t", "\n", "  \t\n  "])
    def test_whitespace_only_returns_none(self, value):
        assert parse_language_selection(value) is None


# ---------------------------------------------------------------------------
# test_parse_unrecognised_input — random text returns None
# ---------------------------------------------------------------------------


class TestParseUnrecognisedInput:
    """Unrecognised text returns None."""

    @pytest.mark.parametrize(
        "value", ["hello", "xyz", "Start", "foo bar", "please help", "random123"]
    )
    def test_unrecognised_returns_none(self, value):
        assert parse_language_selection(value) is None


# ---------------------------------------------------------------------------
# test_parse_numeric_not_a_number — "abc", "1.5", "one" not treated as numbers
# ---------------------------------------------------------------------------


class TestParseNumericNotANumber:
    """Non-integer strings are not treated as numeric selections."""

    @pytest.mark.parametrize("value", ["abc", "1.5", "one", "3.0", "two"])
    def test_not_a_number(self, value):
        assert parse_language_selection(value) is None


# ---------------------------------------------------------------------------
# test_parse_return_type_tuple — valid match returns 2-tuple of strings
# ---------------------------------------------------------------------------


class TestParseReturnTypeTuple:
    """Valid matches return a 2-tuple of strings."""

    def test_return_is_tuple(self):
        result = parse_language_selection("1")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_return_elements_are_strings(self):
        result = parse_language_selection("hi")
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)


# ---------------------------------------------------------------------------
# test_parse_return_type_none — invalid match returns exactly None
# ---------------------------------------------------------------------------


class TestParseReturnTypeNone:
    """Invalid matches return exactly None (not False, not empty tuple)."""

    def test_returns_none_not_falsy(self):
        result = parse_language_selection("xyz")
        assert result is None

    def test_returns_none_for_empty(self):
        result = parse_language_selection("")
        assert result is None


# ---------------------------------------------------------------------------
# test_parse_code_priority — "hi" matches code, not treated as greeting
# ---------------------------------------------------------------------------


class TestParseCodePriority:
    """Language code match takes priority over other strategies."""

    def test_hi_matches_hindi_code(self):
        # "hi" is both the Hindi code AND could be an English greeting
        # Language code match should take priority
        result = parse_language_selection("hi")
        assert result == ("Hindi", "hi")

    def test_or_matches_odia_code(self):
        # "or" is both the Odia code AND an English word
        result = parse_language_selection("or")
        assert result == ("Odia", "or")

    def test_as_matches_assamese_code(self):
        # "as" is both the Assamese code AND an English word
        result = parse_language_selection("as")
        assert result == ("Assamese", "as")
