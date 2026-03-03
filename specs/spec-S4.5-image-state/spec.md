# Spec S4.5 — Image State

## Overview
The `_handle_image_state()` handler processes incoming messages when a user is in `WAITING_FOR_IMAGE` state. It validates that the message contains an image attachment (`NumMedia > 0` and `MediaContentType` starts with `image/`). If a valid image is present, it sends a "please wait" acknowledgement, transitions the session to `PROCESSING`, and invokes an async pipeline placeholder hook (to be wired with the full extraction/translation pipeline in Phase 10 — S10.1). If no media or a non-image attachment is received, it prompts the user to send a photo. This replaces the S4.2 stub implementation.

## Dependencies
- **S4.2** — `_dispatch()`, `_save_session()`, `_delete_session()`, session helpers
- **S3.3** — `send_text_message()` (send acknowledgement, error, and completion messages)

## Target Location
`backend/app/api/webhooks.py`

---

## Functional Requirements

### FR-1: Validate image attachment present
- **What**: Check `payload.num_media > 0` to confirm the user attached media.
- **Inputs**: `payload.num_media` (int), `payload.media_url` (str | None), `payload.media_content_type` (str | None)
- **Outputs**: Boolean decision — proceed to image processing or prompt for image
- **Edge cases**: `num_media=0` with text body → not an image. `num_media > 0` but `media_content_type is None` → treat as invalid.

### FR-2: Validate media content type is image
- **What**: After confirming media is attached, verify `payload.media_content_type` starts with `"image/"` (case-insensitive). This accepts `image/jpeg`, `image/png`, `image/webp`, etc. while rejecting PDFs, audio, video, and other file types.
- **Inputs**: `payload.media_content_type` (str | None)
- **Outputs**: Boolean — valid image type or not
- **Edge cases**: `media_content_type="application/pdf"` → invalid. `media_content_type="IMAGE/JPEG"` → valid (case-insensitive). `media_content_type=None` → invalid.

### FR-3: Send acknowledgement message on valid image
- **What**: When a valid image is received, send an acknowledgement message informing the user that translation is in progress and will take 20–30 seconds. Uses `send_text_message()` from S3.3.
- **Inputs**: `payload.from_number`
- **Outputs**: Twilio message sent via `send_text_message()`
- **Edge cases**: If `send_text_message()` raises, exception propagates to webhook error handler

### FR-4: Acknowledgement message constant
- **What**: Define a module-level constant `PROCESSING_ACK_MESSAGE` containing the "please wait" text sent when a valid image is received.
- **Inputs**: None
- **Outputs**: `str` constant
- **Content**: Must mention that translation is in progress and give an estimated wait time (~20–30 seconds).

### FR-5: Transition session to PROCESSING status
- **What**: After sending the acknowledgement, update the session status to `PROCESSING` to prevent duplicate processing if the user sends another message. Preserve `language_code`, `language_name`, `request_id`, and `created_at` from the existing session. Save via `_save_session()`.
- **Inputs**: Existing `SessionState`, `payload.from_number`, Redis client
- **Outputs**: Updated session saved to Redis with `status=PROCESSING`
- **Edge cases**: Must preserve all existing session fields (language, request_id, created_at)

### FR-6: Pipeline placeholder hook
- **What**: After setting the session to PROCESSING, call a placeholder async function `_run_pipeline()` that will be replaced in S10.1 with the full extraction → translation → TTS pipeline. The placeholder logs that the pipeline is not yet implemented and sends a "coming soon" message. It also cleans up the session (deletes it) after completing so the user can start a new conversation.
- **Inputs**: `payload: WebhookPayload`, `session: SessionState`, `request_id: str`, `redis`
- **Outputs**: Placeholder message sent, session deleted from Redis
- **Edge cases**: Pipeline errors should be caught gracefully (Phase 10 will add proper error handling)

### FR-7: Handle no media attached
- **What**: When `payload.num_media == 0` (user sent text instead of an image while in WAITING_FOR_IMAGE state), send a message reminding them to send a prescription photo. Do NOT change session state.
- **Inputs**: `payload.from_number`, `payload.body`
- **Outputs**: Reminder message sent via `send_text_message()`
- **Edge cases**: Empty body should also trigger this path

### FR-8: No-image prompt constant
- **What**: Define a module-level constant `NO_IMAGE_MESSAGE` containing the reminder text when no image is attached.
- **Inputs**: None
- **Outputs**: `str` constant
- **Content**: Must ask user to send/photograph a prescription image.

### FR-9: Handle non-image media type
- **What**: When `payload.num_media > 0` but `media_content_type` does not start with `"image/"`, send a message informing the user that only image files are supported. Do NOT change session state.
- **Inputs**: `payload.from_number`, `payload.media_content_type`
- **Outputs**: Error message sent via `send_text_message()`
- **Edge cases**: PDFs, audio clips, video files, documents

### FR-10: Unsupported media constant
- **What**: Define a module-level constant `UNSUPPORTED_MEDIA_MESSAGE` for non-image attachments.
- **Inputs**: None
- **Outputs**: `str` constant
- **Content**: Must tell user only photo/image files are supported and ask them to send a photo instead.

### FR-11: Logging with request_id
- **What**: Log all handler operations using Loguru with `request_id` in context. Log: handler entry, validation result (valid image / no media / wrong type), acknowledgement sent, session updated to PROCESSING, pipeline invoked. Never log raw phone numbers or media URLs (PHI-safe).
- **Inputs**: `request_id`
- **Outputs**: Structured log lines with `request_id`
- **Edge cases**: Log `media_content_type` on invalid type (not PHI). Never log `media_url` (could contain patient data).

### FR-12: Function signature compatibility
- **What**: The implemented `_handle_image_state()` must maintain the same signature as the S4.2 stub: `async def _handle_image_state(payload: WebhookPayload, session: SessionState, request_id: str, redis) -> None`. No return value — all effects are side-effect based.
- **Inputs**: `payload: WebhookPayload`, `session: SessionState`, `request_id: str`, `redis` (async Redis client)
- **Outputs**: `None`

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_handle_image_state()` validates `num_media > 0` before processing
- [ ] **Outcome 2**: `_handle_image_state()` validates `media_content_type` starts with `"image/"` (case-insensitive)
- [ ] **Outcome 3**: Valid image → acknowledgement message sent with estimated wait time
- [ ] **Outcome 4**: Valid image → session updated to `status=PROCESSING` with all fields preserved
- [ ] **Outcome 5**: Valid image → pipeline placeholder invoked and session cleaned up
- [ ] **Outcome 6**: No media → `NO_IMAGE_MESSAGE` sent, session unchanged
- [ ] **Outcome 7**: Non-image media → `UNSUPPORTED_MEDIA_MESSAGE` sent, session unchanged
- [ ] **Outcome 8**: `PROCESSING_ACK_MESSAGE` constant exists and mentions wait time
- [ ] **Outcome 9**: `NO_IMAGE_MESSAGE` constant exists and asks for prescription photo
- [ ] **Outcome 10**: `UNSUPPORTED_MEDIA_MESSAGE` constant exists and mentions only images supported
- [ ] **Outcome 11**: Session `language_code`, `language_name`, `request_id`, `created_at` preserved during PROCESSING transition
- [ ] **Outcome 12**: All log lines include `request_id` context
- [ ] **Outcome 13**: No raw phone numbers or media URLs appear in log output (PHI-safe)
- [ ] **Outcome 14**: Function signature matches S4.2 stub (`payload, session, request_id, redis`)
- [ ] **Outcome 15**: Existing dispatch tests (S4.2) continue to pass after replacing the stub

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

#### Constants
1. **test_processing_ack_message_exists**: `PROCESSING_ACK_MESSAGE` is importable from `backend.app.api.webhooks`
2. **test_processing_ack_message_mentions_wait**: `PROCESSING_ACK_MESSAGE` mentions wait time or "please wait"
3. **test_no_image_message_exists**: `NO_IMAGE_MESSAGE` is importable and non-empty
4. **test_no_image_message_mentions_photo**: `NO_IMAGE_MESSAGE` mentions photo or prescription image
5. **test_unsupported_media_message_exists**: `UNSUPPORTED_MEDIA_MESSAGE` is importable and non-empty

#### Valid image — acknowledgement & session
6. **test_valid_image_sends_ack**: Valid image payload → `send_text_message()` called with `PROCESSING_ACK_MESSAGE`
7. **test_valid_image_updates_session_to_processing**: Valid image → session saved with `status=PROCESSING`
8. **test_valid_image_preserves_language_code**: Updated session retains `language_code` from original session
9. **test_valid_image_preserves_language_name**: Updated session retains `language_name` from original session
10. **test_valid_image_preserves_request_id**: Updated session retains `request_id` from original session
11. **test_valid_image_preserves_created_at**: Updated session retains `created_at` from original session

#### Valid image — pipeline placeholder
12. **test_valid_image_calls_pipeline_placeholder**: Valid image → `_run_pipeline()` is called
13. **test_valid_image_pipeline_cleans_session**: After pipeline placeholder, session is deleted from Redis

#### No media attached
14. **test_no_media_sends_reminder**: `num_media=0` → `send_text_message()` called with `NO_IMAGE_MESSAGE`
15. **test_no_media_does_not_change_session**: `num_media=0` → `_save_session()` NOT called

#### Non-image media
16. **test_non_image_media_sends_error**: `num_media=1` with `media_content_type="application/pdf"` → `UNSUPPORTED_MEDIA_MESSAGE` sent
17. **test_non_image_media_does_not_change_session**: Non-image media → `_save_session()` NOT called

#### Error propagation
18. **test_image_propagates_send_error**: If `send_text_message()` raises, exception propagates

#### Logging
19. **test_image_logs_with_request_id**: Handler logs include `request_id` in context
20. **test_image_logs_no_raw_phone_or_media_url**: Log output does not contain raw phone numbers or media URLs

### Mocking Strategy
- **send_text_message**: `unittest.mock.patch("backend.app.api.webhooks.send_text_message")` — verify call args and message constants
- **_save_session**: `unittest.mock.patch("backend.app.api.webhooks._save_session")` — verify session updates and field preservation
- **_delete_session**: `unittest.mock.patch("backend.app.api.webhooks._delete_session")` — verify session cleanup after pipeline
- **_run_pipeline**: `unittest.mock.patch("backend.app.api.webhooks._run_pipeline")` — verify pipeline placeholder is called with correct args
- **Redis**: `AsyncMock` with `set()`, `get()`, `delete()` methods

### Coverage Expectation
- All three branches covered: valid image, no media, non-image media
- Session mutation verified on valid image path, no mutation on invalid paths
- Pipeline placeholder invocation verified
- Session cleanup after pipeline verified
- Error propagation paths verified
- PHI-safe logging confirmed (no phone numbers, no media URLs)

---

## References
- roadmap.md — Phase 4: Webhook State Machine, S4.5
- `backend/app/api/webhooks.py` — S4.2 stub to be replaced
- `backend/app/services/whatsapp.py` — `send_text_message()`
- `backend/app/models/schemas.py` — `SessionState`, `SessionStatus`, `WebhookPayload`
- S10.1 — Pipeline wiring (will replace `_run_pipeline()` placeholder)
