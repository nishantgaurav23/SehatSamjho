# Spec S3.5 — Send Audio Message

## Overview
Async Twilio WhatsApp media message sender. Sends an S3 presigned audio URL as a WhatsApp media message via Twilio. Falls back to a text-only notification if the media send fails. This completes the WhatsApp Channel phase by providing the audio delivery primitive used by Phase 9 (TTS & Audio Delivery).

## Dependencies
- **S3.3** — `send_text_message()` (used as fallback when media fails)

## Target Location
- `backend/app/services/whatsapp.py`

---

## Functional Requirements

### FR-1: `send_audio_message()`
- **What**: Async function that sends a WhatsApp media message containing an audio file via Twilio.
- **Signature**: `async def send_audio_message(to: str, media_url: str, caption: str | None = None) -> str`
- **Inputs**:
  - `to` — recipient in WhatsApp format (e.g. `"whatsapp:+919876543210"`)
  - `media_url` — publicly accessible URL to the audio file (S3 presigned URL)
  - `caption` — optional text caption sent alongside the audio (e.g. "Here is your prescription audio summary")
- **Outputs**: Twilio message SID string on success
- **Behavior**:
  - Validates `to` and `media_url` are non-empty (raises `ValueError` if empty/whitespace)
  - Uses lazy `_get_twilio_client()` singleton (already exists from S3.3)
  - Calls `client.messages.create()` via `asyncio.to_thread()` with `media_url=[media_url]` parameter
  - Includes `body=caption` if caption is provided (Twilio requires body with media for WhatsApp)
  - If caption is None, sends a default body: `"Audio summary of your prescription"`
- **Edge cases**:
  - Empty/whitespace `to` → `ValueError`
  - Empty/whitespace `media_url` → `ValueError`
  - Twilio API error → retry via tenacity, then re-raise

### FR-2: Retry with Tenacity
- **What**: Retry on transient Twilio API errors, consistent with `send_text_message()` pattern.
- **Retry config**: 3 attempts, exponential backoff (min=2s, max=10s), retry only on `TwilioRestException`.
- **Behavior**: Uses `@retry` decorator identical to `send_text_message()`.

### FR-3: Graceful Fallback
- **What**: A wrapper function `send_audio_message_with_fallback()` that attempts audio delivery and falls back to text-only if media send fails.
- **Signature**: `async def send_audio_message_with_fallback(to: str, media_url: str, fallback_text: str, caption: str | None = None) -> tuple[str, bool]`
- **Inputs**:
  - `to` — recipient
  - `media_url` — audio URL
  - `fallback_text` — text to send if audio delivery fails
  - `caption` — optional caption for the audio message
- **Outputs**: Tuple of `(message_sid, audio_sent)` where `audio_sent` is True if media was delivered, False if fallback was used.
- **Behavior**:
  - Try `send_audio_message(to, media_url, caption)` → return `(sid, True)`
  - On any exception (after retries exhausted): log warning, call `send_text_message(to, fallback_text)` → return `(sid, False)`
  - If fallback also fails: let the exception propagate (caller handles)

### FR-4: PHI-Safe Logging
- **What**: Never log raw phone numbers or audio URLs (may contain patient data in path).
- **Behavior**:
  - Log SHA-256 hash of `to` (first 12 chars), same pattern as `send_text_message()`
  - Log `media_url_domain` (just the domain portion) — never the full presigned URL (contains S3 signature)
  - Log `caption_length` (not caption text)
  - Log `message_sid` on success
  - Log `error` string on failure

---

## Tangible Outcomes

- [ ] **Outcome 1**: `send_audio_message("whatsapp:+91...", "https://s3.amazonaws.com/bucket/audio/test.ogg")` successfully calls Twilio `messages.create()` with `media_url` parameter and returns a message SID
- [ ] **Outcome 2**: Empty `to` or `media_url` raises `ValueError` before any API call
- [ ] **Outcome 3**: Transient `TwilioRestException` is retried up to 3 times with exponential backoff
- [ ] **Outcome 4**: `send_audio_message_with_fallback()` returns `(sid, False)` and sends text when audio fails
- [ ] **Outcome 5**: No raw phone numbers, full media URLs, or caption text appear in log output — only hashed/truncated values

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

1. **test_send_audio_message_success**: Mock Twilio client, verify `messages.create()` called with correct `media_url=[url]` param, returns SID
2. **test_send_audio_message_with_caption**: Verify caption is passed as `body` parameter
3. **test_send_audio_message_default_caption**: When caption is None, default body text is used
4. **test_send_audio_message_empty_to_raises**: Empty `to` raises `ValueError`
5. **test_send_audio_message_empty_media_url_raises**: Empty `media_url` raises `ValueError`
6. **test_send_audio_message_whitespace_to_raises**: Whitespace-only `to` raises `ValueError`
7. **test_send_audio_message_whitespace_media_url_raises**: Whitespace-only `media_url` raises `ValueError`
8. **test_send_audio_message_retry_on_twilio_error**: First call raises `TwilioRestException`, second succeeds — verify 2 calls made
9. **test_send_audio_message_exhausted_retries**: All 3 attempts fail — `TwilioRestException` re-raised
10. **test_send_audio_message_uses_twilio_singleton**: Verify `_get_twilio_client()` is called (not a new client)
11. **test_send_audio_message_uses_asyncio_to_thread**: Verify Twilio blocking call is wrapped in `asyncio.to_thread()`
12. **test_fallback_audio_success**: `send_audio_message_with_fallback()` succeeds on first try — returns `(sid, True)`
13. **test_fallback_audio_fails_sends_text**: Audio fails, fallback text sent — returns `(sid, False)`
14. **test_fallback_both_fail_propagates**: Both audio and text fail — exception propagates
15. **test_logging_phi_safe_no_raw_phone**: Verify log output contains hash, not raw phone
16. **test_logging_phi_safe_no_full_url**: Verify log output contains domain only, not full presigned URL

### Mocking Strategy
- Mock `_get_twilio_client()` → return a mock `Client` with `messages.create()` returning a mock message with `.sid`
- Mock `asyncio.to_thread` to execute synchronously in tests (or mock at Twilio level)
- Mock `send_text_message` in fallback tests (already tested in S3.3)
- Mock `backend.app.core.config.settings` for `TWILIO_WHATSAPP_FROM`
- Use `loguru` sink capture to verify PHI-safe logging

### Coverage Expectation
- All public functions (`send_audio_message`, `send_audio_message_with_fallback`) have tests
- Validation edge cases (empty/whitespace inputs) covered
- Retry behavior covered (success after retry, exhausted retries)
- Fallback paths covered (audio success, audio fail + text success, both fail)
- PHI-safe logging verified

---

## References
- `roadmap.md` — S3.5 spec row
- `backend/app/services/whatsapp.py` — existing send_text_message pattern
- `backend/tests/services/test_send_text_message.py` — testing patterns to follow
- `design.md`, `requirements.md`
