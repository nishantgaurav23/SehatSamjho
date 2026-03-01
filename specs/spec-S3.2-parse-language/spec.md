# Spec S3.2 — Parse Language Selection

## Overview
`parse_language_selection()` accepts raw WhatsApp user input (a number 1–8, a language code like "hi", or a language name like "Hindi") and returns a `(language_name, language_code)` tuple if the input matches a supported language, or `None` if unrecognised. All matching is case-insensitive. This function is the parsing layer between the user's WhatsApp message body and the session state machine (S4.4).

## Dependencies
- **S3.1** — `SUPPORTED_LANGUAGES` dict and `TOP_LANGUAGES` list (already implemented in `backend/app/services/whatsapp.py`)

## Target Location
- `backend/app/services/whatsapp.py` (add to existing file)

---

## Functional Requirements

### FR-1: Parse numeric input (1–8)
- **What**: When user sends a digit "1" through "8", map it to the corresponding language in `TOP_LANGUAGES` (1-indexed).
- **Inputs**: String like "1", "3", "8". Whitespace-stripped.
- **Outputs**: `(language_name, language_code)` tuple, e.g. `("Hindi", "hi")` for "1".
- **Edge cases**: "0", "9", "99", negative numbers, non-numeric strings — all return `None`. Leading/trailing whitespace is stripped.

### FR-2: Parse language code input
- **What**: When user sends a valid language code (e.g. "hi", "ta", "kok"), match against `SUPPORTED_LANGUAGES` keys.
- **Inputs**: String like "hi", "TA", "kn". Case-insensitive.
- **Outputs**: `(language_name, language_code)` tuple, e.g. `("Tamil", "ta")` for "TA".
- **Edge cases**: Unknown codes like "xx" → `None`. Empty string → `None`.

### FR-3: Parse language name input
- **What**: When user sends a language name (English name or native display_name), match against `SUPPORTED_LANGUAGES` entries.
- **Inputs**: String like "Hindi", "tamil", "বাংলা". Case-insensitive for English names.
- **Outputs**: `(language_name, language_code)` tuple, e.g. `("Bengali", "bn")` for "বাংলা".
- **Edge cases**: Partial names like "Hin" → `None` (exact match only). Names not in the dict → `None`.

### FR-4: Input sanitization
- **What**: Strip leading/trailing whitespace before matching. Handle empty string and `None`-like inputs gracefully.
- **Inputs**: "  hi  ", "", " ", random text like "hello world".
- **Outputs**: Whitespace-stripped match or `None`.

### FR-5: Return type
- **What**: Function signature: `def parse_language_selection(user_input: str) -> tuple[str, str] | None`
- **Outputs**: `(language_name, language_code)` on match; `None` on no match.
- **Priority**: If input matches multiple strategies (e.g. "hi" matches both code "hi" and could be English text), language code match takes priority, then number, then name.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `parse_language_selection("1")` returns `("Hindi", "hi")`
- [ ] **Outcome 2**: `parse_language_selection("ta")` returns `("Tamil", "ta")`
- [ ] **Outcome 3**: `parse_language_selection("Tamil")` returns `("Tamil", "ta")`
- [ ] **Outcome 4**: `parse_language_selection("তমিল")` or display_name match returns correct tuple
- [ ] **Outcome 5**: `parse_language_selection("xyz")` returns `None`
- [ ] **Outcome 6**: `parse_language_selection("")` returns `None`
- [ ] **Outcome 7**: `parse_language_selection("  3  ")` returns `("Tamil", "ta")` (whitespace stripped)
- [ ] **Outcome 8**: `parse_language_selection("8")` returns `("Malayalam", "ml")` (last top language)
- [ ] **Outcome 9**: `parse_language_selection("9")` returns `None` (out of range)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_parse_numeric_valid**: Each number 1–8 maps to the correct TOP_LANGUAGES entry
2. **test_parse_numeric_out_of_range**: "0", "9", "99", "-1" all return `None`
3. **test_parse_language_code_valid**: All 22 language codes return correct `(name, code)` tuple
4. **test_parse_language_code_case_insensitive**: "HI", "Ta", "KOK" all match correctly
5. **test_parse_language_name_english**: "Hindi", "tamil", "BENGALI" match correctly
6. **test_parse_language_name_display**: Native script display_name matches (e.g. "हिन्दी" → Hindi)
7. **test_parse_whitespace_stripping**: "  hi  ", " 1 " work correctly
8. **test_parse_empty_string**: "" returns `None`
9. **test_parse_none_like**: Whitespace-only " " returns `None`
10. **test_parse_unrecognised_input**: "hello", "xyz", "Start", "foo bar" all return `None`
11. **test_parse_numeric_not_a_number**: "abc", "1.5", "one" not treated as numbers
12. **test_parse_return_type_tuple**: Valid matches return a 2-tuple of strings
13. **test_parse_return_type_none**: Invalid matches return exactly `None`
14. **test_parse_code_priority_over_name**: If input "hi" matches code "hi" (Hindi), it should return Hindi (code match takes priority)

### Mocking Strategy
- No external services needed — this is a pure function operating on in-memory data structures
- No mocking required

### Coverage Expectation
- 100% branch coverage of `parse_language_selection()`
- All 22 language codes tested
- All 8 numeric selections tested
- Edge cases: empty, whitespace, out-of-range, unrecognised text

---

## References
- `roadmap.md` — S3.2 row
- `backend/app/services/whatsapp.py` — S3.1 implementation (SUPPORTED_LANGUAGES, TOP_LANGUAGES)
- `backend/tests/services/test_supported_languages.py` — S3.1 test patterns
