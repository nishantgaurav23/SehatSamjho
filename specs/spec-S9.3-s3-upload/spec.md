# Spec S9.3 — S3 Upload

## Overview
Uploads Bhashini TTS audio bytes to AWS S3 and returns a presigned URL for WhatsApp delivery. Uses `boto3.client("s3").put_object()` wrapped in `asyncio.to_thread` (boto3 is synchronous). Each audio file is stored with a UUID key under `audio/` prefix as `.ogg`, with S3 object expiry metadata. The presigned URL expires after 3600 seconds (1 hour).

## Dependencies
- **S1.3** (pydantic-settings config) — provides `settings.AWS_ACCESS_KEY_ID`, `settings.AWS_SECRET_ACCESS_KEY`, `settings.S3_BUCKET`
- **S9.2** (text_to_speech) — provides audio bytes input

## Target Location
`backend/app/services/tts.py`

---

## Functional Requirements

### FR-1: Lazy S3 client singleton
- **What**: `_get_s3_client()` creates a `boto3.client("s3")` using credentials from `settings`. Lazy-initialized module-level singleton, with `_reset_s3_client()` for testing.
- **Inputs**: None (reads `settings.AWS_ACCESS_KEY_ID`, `settings.AWS_SECRET_ACCESS_KEY`)
- **Outputs**: `boto3.client("s3")` instance
- **Edge cases**: Missing credentials should raise boto3 errors (not our concern — config validated at S1.3)

### FR-2: `_upload_to_s3()` function
- **What**: Accepts audio bytes and an optional `request_id`. Generates a UUID-based S3 key (`audio/{uuid4()}.ogg`). Calls `s3_client.put_object()` via `asyncio.to_thread()` (since boto3 is blocking). Sets `ContentType: audio/ogg`. Returns a presigned URL with 3600s expiry.
- **Inputs**: `audio_bytes: bytes`, `request_id: str = ""`
- **Outputs**: `str` — presigned URL
- **Edge cases**:
  - Empty audio bytes → raise `ValueError`
  - S3 `put_object` failure → raise `S3UploadError` with details
  - `generate_presigned_url` failure → raise `S3UploadError`

### FR-3: S3 object key format
- **What**: Key must be `audio/{uuid4()}.ogg` — unique per upload, under the `audio/` prefix. ContentType is `audio/ogg`.
- **Inputs**: None (generated internally)
- **Outputs**: Key string matching pattern `audio/<uuid>.ogg`

### FR-4: Presigned URL generation
- **What**: After `put_object` succeeds, call `s3_client.generate_presigned_url("get_object", ...)` with `ExpiresIn=3600`. Return the URL string.
- **Inputs**: Bucket name from `settings.S3_BUCKET`, S3 key from FR-3
- **Outputs**: Presigned URL string (https://...)

### FR-5: S3UploadError custom exception
- **What**: New exception class for S3 upload failures. Includes `message` attribute.
- **Inputs**: Error message string
- **Outputs**: Exception with `.message`

### FR-6: Logging
- **What**: Log S3 upload start, success (with key + URL length), and failure. Always include `request_id`. Never log audio content or full presigned URL (contains credentials).
- **Inputs**: request_id, key, timing
- **Outputs**: Loguru log entries

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_get_s3_client()` returns a boto3 S3 client using settings credentials (lazy singleton)
- [ ] **Outcome 2**: `_reset_s3_client()` clears the singleton for test isolation
- [ ] **Outcome 3**: `_upload_to_s3(audio_bytes, request_id)` uploads bytes via `put_object` in `asyncio.to_thread`
- [ ] **Outcome 4**: S3 key matches pattern `audio/{uuid}.ogg` with ContentType `audio/ogg`
- [ ] **Outcome 5**: Returns presigned URL with 3600s expiry
- [ ] **Outcome 6**: Empty `audio_bytes` raises `ValueError`
- [ ] **Outcome 7**: S3 errors raise `S3UploadError`
- [ ] **Outcome 8**: Logging includes request_id, never logs audio content or full presigned URL

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_s3_upload_error_class**: S3UploadError has message attribute, is Exception subclass
2. **test_get_s3_client_returns_client**: _get_s3_client() returns a boto3 S3 client
3. **test_get_s3_client_singleton**: Second call returns same instance
4. **test_get_s3_client_uses_settings**: Client created with correct credentials from settings
5. **test_reset_s3_client**: _reset_s3_client() clears singleton, next call creates new
6. **test_upload_to_s3_imports**: Function is async, importable, correct signature
7. **test_upload_to_s3_empty_bytes_raises_value_error**: Empty bytes raises ValueError
8. **test_upload_to_s3_calls_put_object**: put_object called with correct bucket, key, body, content type
9. **test_upload_to_s3_key_format**: S3 key matches `audio/{uuid}.ogg` pattern
10. **test_upload_to_s3_uses_asyncio_to_thread**: put_object and presigned URL wrapped in asyncio.to_thread
11. **test_upload_to_s3_content_type**: ContentType is `audio/ogg`
12. **test_upload_to_s3_presigned_url**: generate_presigned_url called with get_object, correct bucket/key, ExpiresIn=3600
13. **test_upload_to_s3_returns_presigned_url**: Returns the presigned URL string
14. **test_upload_to_s3_put_object_failure**: S3 ClientError on put_object raises S3UploadError
15. **test_upload_to_s3_presigned_url_failure**: Error on generate_presigned_url raises S3UploadError
16. **test_upload_to_s3_logging_start**: Logs upload start with request_id
17. **test_upload_to_s3_logging_success**: Logs success with request_id and key
18. **test_upload_to_s3_logging_no_audio_content**: Logs never contain audio bytes
19. **test_upload_to_s3_logging_no_full_url**: Logs never contain full presigned URL (has credentials)
20. **test_upload_to_s3_default_request_id**: Works with default empty request_id

### Mocking Strategy
- `boto3.client("s3")` — mock via `unittest.mock.patch` on the boto3 import in tts module
- `asyncio.to_thread` — mock to verify it wraps the blocking boto3 calls
- `uuid.uuid4()` — mock to produce deterministic keys for assertions
- `settings` — mock at `backend.app.core.config.settings` for credential tests

### Coverage Expectation
- All public functions have at least one test; edge cases covered
- 20 tests targeting _upload_to_s3, _get_s3_client, _reset_s3_client, S3UploadError

---

## References
- roadmap.md Phase 9 — TTS & Audio Delivery
- S1.3 spec (settings: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET)
- S9.2 spec (text_to_speech returns audio bytes)
- boto3 S3 client API: put_object, generate_presigned_url
