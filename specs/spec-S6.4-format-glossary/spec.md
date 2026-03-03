# Spec S6.4 — format glossary context

## Overview

Formats matched glossary entries (from `lookup_terms()`) into a structured text block suitable for injection into the Claude Sonnet 4.6 translation system prompt. Each entry becomes a line like `"Term: X -> {language}: Y"`. The output is capped at ~500 tokens of context to stay within prompt budget.

## Dependencies

- **S6.3** — `lookup_terms()` (provides `list[GlossaryEntry]`)

## Target Location

`backend/app/services/glossary.py`

---

## Functional Requirements

### FR-1: Function signature
- **What**: `format_glossary_context(entries: list[GlossaryEntry], language_name: str) -> str`
- **Inputs**: `entries` — list of `GlossaryEntry` objects (from `lookup_terms()`); `language_name` — display name of the target language (e.g. "Hindi", "Tamil")
- **Outputs**: A single string block ready for injection into a Claude system prompt
- **Edge cases**: Empty list returns empty string; `language_name` is empty string

### FR-2: Line formatting
- **What**: Each `GlossaryEntry` produces one line: `"Term: {term} -> {language_name}: {vernacular} ({explanation})"`
- **Inputs**: Single `GlossaryEntry` with `term`, `vernacular`, `explanation` fields
- **Outputs**: Formatted string line
- **Edge cases**: Entries with very long explanation or vernacular text

### FR-3: Block structure
- **What**: Lines are joined with newlines. The block is wrapped with a header line: `"--- Medical Glossary ({language_name}) ---"` and a trailing `"---"` separator
- **Inputs**: List of formatted lines
- **Outputs**: Complete block string with header and footer

### FR-4: Token budget enforcement (~500 tokens)
- **What**: Approximate token count using character heuristic (1 token ~ 4 chars for English, ~2 chars for Indic scripts). If the formatted block exceeds ~2000 characters, truncate by dropping entries from the end and appending `"... ({N} more terms omitted)"`
- **Inputs**: Full formatted block
- **Outputs**: Truncated block if over budget, full block otherwise
- **Edge cases**: Exactly at limit, single entry exceeding limit

### FR-5: Pure function (no I/O)
- **What**: `format_glossary_context()` is a pure function — no Redis, no async, no side effects. It takes in-memory data and returns a string.
- **Inputs**: Already-resolved `GlossaryEntry` list
- **Outputs**: String

---

## Tangible Outcomes

- [ ] **Outcome 1**: `format_glossary_context([], "Hindi")` returns `""`
- [ ] **Outcome 2**: `format_glossary_context([entry], "Tamil")` returns a block with header, one formatted line, and footer
- [ ] **Outcome 3**: Each line follows format `"Term: {term} -> {language}: {vernacular} ({explanation})"`
- [ ] **Outcome 4**: Block with header `"--- Medical Glossary ({language_name}) ---"` and footer `"---"`
- [ ] **Outcome 5**: Output is truncated with `"... (N more terms omitted)"` when exceeding ~2000 chars
- [ ] **Outcome 6**: Function is synchronous (not async), pure (no I/O), importable from `backend.app.services.glossary`

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

1. **test_import_format_glossary_context**: Function is importable from `backend.app.services.glossary`
2. **test_signature_sync**: Function is a regular (non-async) callable
3. **test_empty_entries_returns_empty_string**: `format_glossary_context([], "Hindi")` == `""`
4. **test_single_entry_format**: One entry produces header + one line + footer
5. **test_line_format_contains_term**: Each line contains `"Term: {term}"`
6. **test_line_format_contains_language_arrow**: Each line contains `"-> {language_name}:"`
7. **test_line_format_contains_vernacular**: Each line contains the vernacular text
8. **test_line_format_contains_explanation**: Each line contains the explanation in parens
9. **test_multiple_entries_all_present**: N entries produce N lines between header/footer
10. **test_header_contains_language_name**: Header line matches `"--- Medical Glossary ({language_name}) ---"`
11. **test_footer_separator**: Block ends with `"---"`
12. **test_entries_order_preserved**: Output lines match input order
13. **test_truncation_over_budget**: When total > 2000 chars, trailing entries are dropped
14. **test_truncation_message**: Truncated output contains `"... (N more terms omitted)"`
15. **test_truncation_keeps_header_footer**: Truncated output still has header and footer
16. **test_no_truncation_under_budget**: Short output is not truncated
17. **test_empty_language_name**: Empty string language_name still works (no crash)
18. **test_duplicate_entries_all_rendered**: Duplicate entries in list are all formatted (no dedup — that's lookup_terms' job)
19. **test_return_type_is_str**: Return value is always `str`
20. **test_no_trailing_newline_on_empty**: Empty input returns `""` not `"\n"`

### Mocking Strategy

- No mocking needed — `format_glossary_context()` is a pure function
- Create `GlossaryEntry` objects directly in test fixtures

### Coverage Expectation

- All public functions have at least one test; edge cases covered
- 20 tests total
