# Checklist — Spec S9.3: S3 Upload

## Phase 1: Setup & Dependencies
- [x] Verify S1.3 (pydantic-settings config) is implemented — provides AWS credentials + S3_BUCKET
- [x] Verify S9.2 (text_to_speech) is implemented — provides audio bytes input
- [x] Locate target file: `backend/app/services/tts.py`
- [x] Confirm `boto3` is in pyproject.toml dependencies

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/services/test_s3_upload.py`
- [x] Write tests for S3UploadError exception class (2 tests)
- [x] Write tests for _get_s3_client singleton + reset (4 tests)
- [x] Write tests for _upload_to_s3 happy path (7 tests)
- [x] Write tests for _upload_to_s3 error paths (3 tests)
- [x] Write tests for logging (4 tests)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Add `S3UploadError` exception class to tts.py
- [x] Implement `_get_s3_client()` lazy singleton using boto3 + settings
- [x] Implement `_reset_s3_client()` for test isolation
- [x] Implement `_upload_to_s3(audio_bytes, request_id)`:
  - [x] Validate non-empty audio_bytes
  - [x] Generate UUID key: `audio/{uuid4()}.ogg`
  - [x] Call `put_object` via `asyncio.to_thread`
  - [x] Call `generate_presigned_url` via `asyncio.to_thread`
  - [x] Log start + success with request_id
  - [x] Handle S3 errors → S3UploadError
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify no import cycles introduced
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 20 tangible outcomes checked
- [x] No hardcoded secrets (AWS creds from settings only)
- [x] Logging includes request_id
- [x] Logs never contain audio content or full presigned URL
- [x] Update roadmap.md status: pending -> done (when ready)
