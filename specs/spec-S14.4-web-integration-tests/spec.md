# S14.4 — Web Integration Tests

## Context
End-to-end integration tests for the web upload flow: upload image via `POST /api/translate`, verify full pipeline executes, verify response format, verify error handling.

## Dependencies
- S14.2 (Web upload API)
- S14.3 (Web frontend)
- S14.1 (Edge TTS fallback)

## Functional Requirements

### FR-1: Happy path integration test
- Upload a valid image with language_code="hi".
- Mock all external services (OpenAI, Anthropic, Edge TTS, S3, Redis).
- Assert response contains: medicines, translated_text, disclaimer, audio_url.
- Assert HTTP 200.

### FR-2: Error path tests
- Non-image file -> 400.
- Unsupported language_code -> 400.
- Missing image -> 422.
- NotMedicalDocumentError from pipeline -> 422.
- ImageNotReadableError from pipeline -> 422.
- TranslationError -> 500.

### FR-3: Frontend page tests
- GET / returns 200 with HTML content.
- HTML contains language dropdown with all 22 options.
- HTML contains file upload form.
- Static CSS/JS files are served.

### FR-4: Edge TTS fallback in web pipeline
- Mock Bhashini as unavailable (empty API key).
- Verify Edge TTS is called as fallback.
- Verify audio_url is returned from S3.

## Test Plan
- 20 tests in `backend/tests/test_web_integration.py`.
- All external services mocked.
