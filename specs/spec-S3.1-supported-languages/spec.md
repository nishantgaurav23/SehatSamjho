# Spec S3.1 — Supported Languages

## Overview

Define the `SUPPORTED_LANGUAGES` constant dictionary in the WhatsApp service module, mapping ISO language codes to structured metadata for all 22 scheduled Indian languages supported by Bhashini TTS. Each entry contains the language's English name, localized display name (in its native script), and Bhashini TTS API code. This dictionary is the single source of truth for language support across the entire application — used by language selection (S3.2), TTS (Phase 9), translation (Phase 7), and glossary (Phase 6).

## Dependencies

- **S2.4** (Pydantic models) — `SessionState` stores `language_code` / `language_name` sourced from this dictionary

## Target Location

- `backend/app/services/whatsapp.py`

---

## Functional Requirements

### FR-1: SUPPORTED_LANGUAGES dictionary

- **What**: Module-level constant `SUPPORTED_LANGUAGES: dict[str, dict[str, str]]` containing all 22 scheduled Indian languages.
- **Structure**: Key = ISO 639 language code (e.g., `"hi"`, `"ta"`, `"kok"`). Value = dict with three keys:
  - `name`: English language name (e.g., `"Hindi"`)
  - `display_name`: Localized name in native script (e.g., `"हिन्दी"`)
  - `bhashini_code`: Bhashini TTS API language code (e.g., `"hi"`)
- **Languages** (all 22 scheduled):

| # | Code | Name | Display Name | Bhashini Code |
|---|------|------|-------------|---------------|
| 1 | `hi` | Hindi | हिन्दी | `hi` |
| 2 | `bn` | Bengali | বাংলা | `bn` |
| 3 | `ta` | Tamil | தமிழ் | `ta` |
| 4 | `te` | Telugu | తెలుగు | `te` |
| 5 | `mr` | Marathi | मराठी | `mr` |
| 6 | `gu` | Gujarati | ગુજરાતી | `gu` |
| 7 | `kn` | Kannada | ಕನ್ನಡ | `kn` |
| 8 | `ml` | Malayalam | മലയാളം | `ml` |
| 9 | `or` | Odia | ଓଡ଼ିଆ | `or` |
| 10 | `pa` | Punjabi | ਪੰਜਾਬੀ | `pa` |
| 11 | `as` | Assamese | অসমীয়া | `as` |
| 12 | `ur` | Urdu | اردو | `ur` |
| 13 | `ks` | Kashmiri | كٲشُر | `ks` |
| 14 | `sd` | Sindhi | سنڌي | `sd` |
| 15 | `kok` | Konkani | कोंकणी | `kok` |
| 16 | `mai` | Maithili | मैथिली | `mai` |
| 17 | `doi` | Dogri | डोगरी | `doi` |
| 18 | `mni` | Manipuri | মণিপুরী | `mni` |
| 19 | `sat` | Santali | ᱥᱟᱱᱛᱟᱲᱤ | `sat` |
| 20 | `ne` | Nepali | नेपाली | `ne` |
| 21 | `brx` | Bodo | बड़ो | `brx` |
| 22 | `sa` | Sanskrit | संस्कृतम् | `sa` |

- **Edge cases**: Dictionary is immutable at runtime (constant, not modified). No empty strings allowed in values.

### FR-2: TOP_LANGUAGES list

- **What**: Module-level constant `TOP_LANGUAGES: list[str]` — the top 8 language codes by user population, used for the initial WhatsApp quick-reply buttons (S3.4).
- **Value**: `["hi", "bn", "ta", "te", "mr", "gu", "kn", "ml"]`
- **Constraint**: All codes must exist in `SUPPORTED_LANGUAGES`.

### FR-3: Helper function `get_language_name()`

- **What**: `get_language_name(code: str) -> str | None` — returns the English name for a valid language code, or `None` if not found.
- **Inputs**: `code` — a string (language code).
- **Outputs**: The `name` field from `SUPPORTED_LANGUAGES[code]`, or `None`.
- **Edge cases**: Empty string → `None`. Invalid code → `None`. Case-insensitive matching (normalize to lowercase).

### FR-4: Helper function `is_supported_language()`

- **What**: `is_supported_language(code: str) -> bool` — returns `True` if the code is in `SUPPORTED_LANGUAGES`.
- **Inputs**: `code` — a string.
- **Outputs**: `True` / `False`.
- **Edge cases**: Empty string → `False`. Case-insensitive.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `SUPPORTED_LANGUAGES` has exactly 22 entries, each with `name`, `display_name`, `bhashini_code` keys
- [ ] **Outcome 2**: `TOP_LANGUAGES` has exactly 8 entries, all present in `SUPPORTED_LANGUAGES`
- [ ] **Outcome 3**: `get_language_name("hi")` returns `"Hindi"`, `get_language_name("xyz")` returns `None`
- [ ] **Outcome 4**: `is_supported_language("ta")` returns `True`, `is_supported_language("")` returns `False`
- [ ] **Outcome 5**: All values in `SUPPORTED_LANGUAGES` have non-empty `name`, `display_name`, `bhashini_code`

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

1. **test_supported_languages_has_22_entries**: Assert `len(SUPPORTED_LANGUAGES) == 22`
2. **test_supported_languages_keys_are_strings**: All keys are non-empty strings
3. **test_supported_languages_values_have_required_keys**: Every value dict has `name`, `display_name`, `bhashini_code`
4. **test_supported_languages_no_empty_values**: No empty strings in any value field
5. **test_supported_languages_contains_hindi**: `"hi"` in dict, name == `"Hindi"`
6. **test_supported_languages_contains_tamil**: `"ta"` in dict, name == `"Tamil"`
7. **test_supported_languages_contains_all_top_8**: All codes from `TOP_LANGUAGES` present
8. **test_top_languages_has_8_entries**: Assert `len(TOP_LANGUAGES) == 8`
9. **test_top_languages_all_in_supported**: Every code in `TOP_LANGUAGES` is a key in `SUPPORTED_LANGUAGES`
10. **test_top_languages_order**: First element is `"hi"` (Hindi, most speakers)
11. **test_get_language_name_valid_code**: `get_language_name("hi")` returns `"Hindi"`
12. **test_get_language_name_invalid_code**: `get_language_name("xyz")` returns `None`
13. **test_get_language_name_empty_string**: `get_language_name("")` returns `None`
14. **test_get_language_name_case_insensitive**: `get_language_name("HI")` returns `"Hindi"`
15. **test_is_supported_language_valid**: `is_supported_language("ta")` returns `True`
16. **test_is_supported_language_invalid**: `is_supported_language("xx")` returns `False`
17. **test_is_supported_language_empty**: `is_supported_language("")` returns `False`
18. **test_is_supported_language_case_insensitive**: `is_supported_language("TA")` returns `True`
19. **test_bhashini_codes_match_keys**: For most languages, `bhashini_code` matches the dict key
20. **test_display_names_are_non_ascii**: Display names for non-Urdu/Kashmiri/Sindhi languages contain non-ASCII characters (native script)

### Mocking Strategy

- No mocking needed — pure data + pure functions, no external services

### Coverage Expectation

- 100% of `SUPPORTED_LANGUAGES`, `TOP_LANGUAGES`, `get_language_name()`, `is_supported_language()`
- All edge cases (empty string, invalid code, case sensitivity) covered

---

## References

- roadmap.md — S3.1 row (Phase 3, WhatsApp Channel)
- design.md, requirements.md — Bhashini TTS 22 Indian languages
- India's 22 Scheduled Languages (Eighth Schedule of the Constitution)
