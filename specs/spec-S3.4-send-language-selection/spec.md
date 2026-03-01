# Spec S3.4 — Send Language Selection

## Overview
Sends a WhatsApp language selection menu to the patient listing the top 8 Indian languages plus a "More" option. Uses Twilio ContentSid for structured quick-reply buttons (max 3 per row) or falls back to a numbered text list. Depends on the SUPPORTED_LANGUAGES/TOP_LANGUAGES constants from S3.1 and the `send_text_message()` helper from S3.3.

## Dependencies
- S3.1 (SUPPORTED_LANGUAGES + TOP_LANGUAGES)
- S3.3 (send_text_message)

## Target Location
`backend/app/services/whatsapp.py`

---

## Functional Requirements

### FR-1: `build_language_menu_text()`
- **What**: Pure function that builds a numbered text list of the top 8 languages for display in WhatsApp.
- **Inputs**: None (reads from `TOP_LANGUAGES` and `SUPPORTED_LANGUAGES` module constants).
- **Outputs**: A formatted string with one line per language: `"{number}. {English name} ({display_name})"`, plus a final line `"9. More languages"`.
- **Edge cases**: Always returns exactly 9 lines (8 languages + "More"). The numbering is 1-indexed and matches `parse_language_selection()` numeric input.

### FR-2: `send_language_selection()`
- **What**: Async function that sends the language menu to a WhatsApp user. Attempts to use Twilio Content Templates (ContentSid) for rich quick-reply buttons if a `TWILIO_CONTENT_SID` setting is available, otherwise falls back to a plain text numbered list via `send_text_message()`.
- **Inputs**: `to: str` (WhatsApp recipient, e.g. `"whatsapp:+919876543210"`).
- **Outputs**: Returns the Twilio message SID string on success.
- **Edge cases**:
  - Empty/whitespace `to` raises `ValueError`.
  - If ContentSid sending fails (TwilioRestException), falls back to text list automatically.
  - Retry behaviour is inherited from `send_text_message()` for the text fallback path.

### FR-3: `send_more_languages()`
- **What**: Async function that sends the remaining 14 languages (all 22 minus the top 8) as a numbered text list when the user selects "More".
- **Inputs**: `to: str` (WhatsApp recipient).
- **Outputs**: Returns the Twilio message SID string on success.
- **Edge cases**:
  - Empty/whitespace `to` raises `ValueError`.
  - The remaining languages are all languages in SUPPORTED_LANGUAGES that are NOT in TOP_LANGUAGES, sorted alphabetically by English name.
  - Each line: `"{code}: {English name} ({display_name})"` — uses language code (not number) since numbers 1-8 are reserved for top languages.

### FR-4: PHI-safe logging
- **What**: All logging must hash phone numbers (SHA-256, first 12 chars) — never log raw phone numbers.
- **Inputs**: Phone number from `to` parameter.
- **Outputs**: Log entries with `to_hash` field.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `build_language_menu_text()` returns a string with exactly 9 lines, numbered 1-9, matching TOP_LANGUAGES order + "More languages"
- [ ] **Outcome 2**: `send_language_selection(to)` sends a WhatsApp message containing the language menu and returns a message SID
- [ ] **Outcome 3**: `send_language_selection(to)` falls back to text list if ContentSid is unavailable or fails
- [ ] **Outcome 4**: `send_more_languages(to)` sends the remaining 14 languages sorted alphabetically by English name
- [ ] **Outcome 5**: Phone numbers are never logged in plaintext — only SHA-256 hashes
- [ ] **Outcome 6**: Empty `to` raises ValueError for both send functions

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

#### `build_language_menu_text()` tests
1. **test_menu_text_has_nine_lines**: Output has exactly 9 lines
2. **test_menu_text_first_line_hindi**: First line is `"1. Hindi (हिन्दी)"`
3. **test_menu_text_last_line_more**: Last line is `"9. More languages"`
4. **test_menu_text_all_top_languages_present**: All 8 TOP_LANGUAGES appear in correct order
5. **test_menu_text_numbering_matches_parse**: Numbers 1-8 correspond to the same languages `parse_language_selection()` would resolve

#### `send_language_selection()` tests
6. **test_send_language_selection_text_fallback**: When no ContentSid configured, calls `send_text_message()` with the menu text
7. **test_send_language_selection_returns_sid**: Returns the message SID from the underlying send call
8. **test_send_language_selection_empty_to_raises**: Empty string raises ValueError
9. **test_send_language_selection_whitespace_to_raises**: Whitespace-only string raises ValueError
10. **test_send_language_selection_content_sid_fallback**: If ContentSid send fails, falls back to text list
11. **test_send_language_selection_logs_hash_not_phone**: Log output contains hashed phone, not raw number

#### `send_more_languages()` tests
12. **test_send_more_languages_sends_14_languages**: Message body contains exactly 14 language entries
13. **test_send_more_languages_excludes_top_8**: None of the TOP_LANGUAGES appear in the output
14. **test_send_more_languages_sorted_alphabetically**: Languages are sorted by English name
15. **test_send_more_languages_uses_code_not_number**: Lines use language codes (e.g. "as: Assamese") not numbers
16. **test_send_more_languages_returns_sid**: Returns message SID
17. **test_send_more_languages_empty_to_raises**: Empty string raises ValueError

### Mocking Strategy
- Mock `send_text_message()` (already tested in S3.3) to avoid real Twilio calls
- Mock `_get_twilio_client()` if testing ContentSid path directly
- Mock `asyncio.to_thread` for ContentSid path
- No need to mock SUPPORTED_LANGUAGES/TOP_LANGUAGES (pure data, already tested in S3.1)

### Coverage Expectation
- All three public functions fully covered
- Both happy path and error/fallback paths for `send_language_selection()`
- Edge cases: empty input, ContentSid failure

---

## References
- roadmap.md (S3.4 row)
- specs/spec-S3.1-supported-languages/spec.md
- specs/spec-S3.3-send-text-message/spec.md
- backend/app/services/whatsapp.py (existing implementation)
