# Spec S4.4 — Language State

## Overview
The `_handle_language_state()` handler processes the user's language selection during the WhatsApp conversation flow. When a user is in `WAITING_FOR_LANGUAGE` state, their message body is parsed via `parse_language_selection()` (S3.2). If valid, the session is updated with the chosen language and transitioned to `WAITING_FOR_IMAGE`, and a prompt to send a prescription photo is sent. If the user types "9" (the "More languages" option), the extended language list is sent. If the input is unrecognised, the language selection menu is re-sent. This replaces the S4.2 stub implementation.

## Dependencies
- **S4.2** — `_dispatch()`, `_save_session()`, `_load_session()`, session helpers
- **S3.2** — `parse_language_selection()` (parse user input into language tuple)
- **S3.3** — `send_text_message()` (send confirmation/prompt messages)
- **S3.4** — `send_language_selection()`, `send_more_languages()` (re-send menus on invalid input or "More")

## Target Location
`backend/app/api/webhooks.py`

---

## Functional Requirements

### FR-1: Parse language from message body
- **What**: Call `parse_language_selection(payload.body)` to attempt parsing the user's input into a `(language_name, language_code)` tuple.
- **Inputs**: `payload.body` (the raw WhatsApp message text)
- **Outputs**: `tuple[str, str] | None` — `(language_name, language_code)` or `None`
- **Edge cases**: Empty body → `None`. Whitespace-only → `None`. Numbers outside 1-8 (except "9") → `None`.

### FR-2: Handle valid language selection
- **What**: When `parse_language_selection()` returns a valid tuple, update the session: set `language_code`, `language_name`, and `status=WAITING_FOR_IMAGE`. Save updated session to Redis via `_save_session()`. Send a confirmation message telling the user to send a prescription photo.
- **Inputs**: Valid `(language_name, language_code)` tuple, existing `SessionState`, Redis client
- **Outputs**: Updated session saved to Redis, confirmation message sent via `send_text_message()`
- **Edge cases**: Session `request_id` and `created_at` must be preserved from the original session

### FR-3: Confirmation message constant
- **What**: Define a module-level constant `IMAGE_PROMPT_MESSAGE` containing the prompt text asking the user to send a prescription photo. Must be clear and patient-friendly.
- **Inputs**: None
- **Outputs**: `str` constant
- **Content**: Must instruct user to send/photograph a prescription. Should mention supported formats (photo/image).

### FR-4: Handle "More languages" request
- **What**: When the user sends "9" (the "More languages" option from the language menu), send the extended language list via `send_more_languages()` and then re-send the main language selection menu. Do NOT change session state — keep `WAITING_FOR_LANGUAGE`.
- **Inputs**: `payload.body` stripped equals "9"
- **Outputs**: Extended list + language menu re-sent, session unchanged
- **Edge cases**: "9" is checked before `parse_language_selection()` since `parse_language_selection("9")` returns `None`

### FR-5: Handle invalid/unrecognised input
- **What**: When `parse_language_selection()` returns `None` (and input is not "9"), send an error message explaining the input was not recognised and re-send the language selection menu. Do NOT change session state.
- **Inputs**: Unrecognised input string
- **Outputs**: Error text + language selection re-sent via `send_language_selection()`
- **Edge cases**: Empty body should still trigger this path. The error message should be friendly and not patronising.

### FR-6: Invalid input message constant
- **What**: Define a module-level constant `LANGUAGE_NOT_RECOGNISED_MESSAGE` containing the friendly error text for unrecognised language input.
- **Inputs**: None
- **Outputs**: `str` constant
- **Content**: Should tell user their choice was not recognised and ask them to try again.

### FR-7: Logging with request_id
- **What**: Log all handler operations using Loguru with `request_id` in context. Log: handler entry, parse result (valid/invalid/more), session update, messages sent. Never log raw phone numbers (PHI-safe).
- **Inputs**: `request_id`
- **Outputs**: Structured log lines with `request_id`
- **Edge cases**: Log the chosen language_name and language_code on success (these are not PHI)

### FR-8: Function signature compatibility
- **What**: The implemented `_handle_language_state()` must maintain the same signature as the S4.2 stub: `async def _handle_language_state(payload: WebhookPayload, session: SessionState, request_id: str, redis) -> None`. No return value — all effects are side-effect based.
- **Inputs**: `payload: WebhookPayload`, `session: SessionState`, `request_id: str`, `redis` (async Redis client)
- **Outputs**: `None`

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_handle_language_state()` parses user input via `parse_language_selection()`
- [ ] **Outcome 2**: Valid language → session updated with `language_code`, `language_name`, `status=WAITING_FOR_IMAGE`
- [ ] **Outcome 3**: Valid language → confirmation message sent prompting user to send prescription photo
- [ ] **Outcome 4**: "9" input → extended language list sent via `send_more_languages()`
- [ ] **Outcome 5**: "9" input → language selection menu re-sent, session state unchanged
- [ ] **Outcome 6**: Invalid input → `LANGUAGE_NOT_RECOGNISED_MESSAGE` sent
- [ ] **Outcome 7**: Invalid input → language selection menu re-sent, session state unchanged
- [ ] **Outcome 8**: `IMAGE_PROMPT_MESSAGE` constant exists and mentions sending a prescription photo
- [ ] **Outcome 9**: `LANGUAGE_NOT_RECOGNISED_MESSAGE` constant exists and is user-friendly
- [ ] **Outcome 10**: Session `request_id` and `created_at` preserved after language update
- [ ] **Outcome 11**: All log lines include `request_id` context
- [ ] **Outcome 12**: No raw phone numbers appear in log output (PHI-safe)
- [ ] **Outcome 13**: Function signature matches S4.2 stub (`payload, session, request_id, redis`)
- [ ] **Outcome 14**: Existing dispatch tests (S4.2) continue to pass after replacing the stub

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

#### Constants
1. **test_image_prompt_message_exists**: `IMAGE_PROMPT_MESSAGE` is importable from `backend.app.api.webhooks`
2. **test_image_prompt_message_mentions_prescription**: `IMAGE_PROMPT_MESSAGE` mentions prescription/photo
3. **test_language_not_recognised_message_exists**: `LANGUAGE_NOT_RECOGNISED_MESSAGE` is importable and non-empty

#### Valid language selection
4. **test_language_calls_parse_language_selection**: Handler calls `parse_language_selection(payload.body)`
5. **test_valid_language_updates_session_status**: Valid language → session saved with `status=WAITING_FOR_IMAGE`
6. **test_valid_language_stores_language_code**: Valid language → session has correct `language_code`
7. **test_valid_language_stores_language_name**: Valid language → session has correct `language_name`
8. **test_valid_language_preserves_request_id**: Updated session retains original `request_id`
9. **test_valid_language_preserves_created_at**: Updated session retains original `created_at`
10. **test_valid_language_sends_image_prompt**: Valid language → `send_text_message()` called with `IMAGE_PROMPT_MESSAGE`

#### More languages
11. **test_more_languages_sends_extended_list**: Input "9" → `send_more_languages()` called
12. **test_more_languages_resends_selection**: Input "9" → `send_language_selection()` called after extended list
13. **test_more_languages_does_not_change_session**: Input "9" → `_save_session()` NOT called (session unchanged)

#### Invalid input
14. **test_invalid_input_sends_error_message**: Unrecognised input → `send_text_message()` called with `LANGUAGE_NOT_RECOGNISED_MESSAGE`
15. **test_invalid_input_resends_language_selection**: Unrecognised input → `send_language_selection()` called
16. **test_invalid_input_does_not_change_session**: Unrecognised input → `_save_session()` NOT called

#### Error propagation
17. **test_language_propagates_send_error**: If `send_text_message()` raises, exception propagates
18. **test_language_propagates_selection_error**: If `send_language_selection()` raises, exception propagates

#### Logging
19. **test_language_logs_with_request_id**: Handler logs include `request_id` in context
20. **test_language_logs_no_raw_phone**: Log output does not contain raw phone numbers

### Mocking Strategy
- **parse_language_selection**: `unittest.mock.patch("backend.app.api.webhooks.parse_language_selection")` — control return value per test
- **send_text_message**: `unittest.mock.patch("backend.app.api.webhooks.send_text_message")` — verify call args
- **send_language_selection**: `unittest.mock.patch("backend.app.api.webhooks.send_language_selection")` — verify re-send on invalid
- **send_more_languages**: `unittest.mock.patch("backend.app.api.webhooks.send_more_languages")` — verify "9" handling
- **_save_session**: `unittest.mock.patch("backend.app.api.webhooks._save_session")` — verify session updates (or spy on Redis mock)
- **Redis**: `AsyncMock` with `set()`, `get()`, `delete()` methods

### Coverage Expectation
- All three branches covered: valid language, "9" (more), invalid input
- Session mutation verified on valid path, no mutation on invalid/more paths
- Message ordering verified
- Error propagation paths verified
- PHI-safe logging confirmed

---

## References
- roadmap.md — Phase 4: Webhook State Machine, S4.4
- `backend/app/api/webhooks.py` — S4.2 stub to be replaced
- `backend/app/services/whatsapp.py` — `parse_language_selection()`, `send_text_message()`, `send_language_selection()`, `send_more_languages()`
- `backend/app/models/schemas.py` — `SessionState`, `SessionStatus`, `WebhookPayload`
