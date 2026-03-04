# Spec S9.1 — Bhashini TTS API Client

## Overview
Implements the low-level Bhashini TTS API client that POSTs to the Bhashini pipeline inference endpoint to convert text into speech audio. The client sends a structured payload specifying the task type (`tts`), source language code, and input text. It receives a response containing base64-encoded audio bytes which are decoded and returned. This is the foundation for all text-to-speech functionality in the system.

## Dependencies
- S1.3 (pydantic-settings config) — `BHASHINI_API_KEY`, `BHASHINI_USER_ID` from `settings`

## Target Location
- `backend/app/services/tts.py`

---

## Functional Requirements

### FR-1: Bhashini Configuration Constants
- **What**: Define module-level constants for the Bhashini TTS API
- **Constants**:
  - `BHASHINI_INFERENCE_URL`: The Bhashini pipeline inference endpoint URL
  - `BHASHINI_TTS_GENDER`: Default voice gender (`"female"`)
- **Edge cases**: URL must be a valid HTTPS endpoint string

### FR-2: Lazy Singleton httpx.AsyncClient
- **What**: Provide `_get_httpx_client()` that returns a reusable `httpx.AsyncClient` for Bhashini API calls, plus `_reset_httpx_client()` for testing
- **Inputs**: None (reads from module-level `_httpx_client`)
- **Outputs**: `httpx.AsyncClient` instance (lazy-initialized)
- **Edge cases**: Thread-safety not required (single async event loop). Reset must set `_httpx_client = None`

### FR-3: Build Bhashini Request Payload
- **What**: `_build_bhashini_payload(text: str, language_code: str)` constructs the JSON payload for the Bhashini inference endpoint
- **Inputs**: `text` (the text to synthesize), `language_code` (ISO 639-1 code, e.g. "hi", "ta")
- **Outputs**: A dict matching Bhashini's expected schema:
  ```json
  {
    "pipelineTasks": [
      {
        "taskType": "tts",
        "config": {
          "language": {
            "sourceLanguage": "<language_code>"
          },
          "gender": "female"
        }
      }
    ],
    "inputData": {
      "input": [
        {
          "source": "<text>"
        }
      ]
    }
  }
  ```
- **Edge cases**: Empty text, very long text (>5000 chars — truncate or let Bhashini handle)

### FR-4: `_call_bhashini()` — POST to Bhashini and Decode Audio
- **What**: `_call_bhashini(text: str, language_code: str, request_id: str = "")` sends the payload to Bhashini and returns raw audio bytes
- **Inputs**: `text`, `language_code`, `request_id` (for logging)
- **Outputs**: `bytes` — decoded audio content from the base64-encoded response
- **Behavior**:
  1. Build payload via `_build_bhashini_payload()`
  2. POST to `BHASHINI_INFERENCE_URL` with headers: `Authorization: <BHASHINI_API_KEY>`, `Content-Type: application/json`, optional `userID: <BHASHINI_USER_ID>`
  3. Parse response JSON: extract audio base64 string from `pipelineResponse[0].output[0].audio[0].audioContent`
  4. Decode base64 → return raw bytes
- **Edge cases**:
  - HTTP 4xx/5xx → raise `BhashiniTTSError`
  - Missing/empty `audioContent` in response → raise `BhashiniTTSError`
  - Timeout (30s default) → raise `BhashiniTTSError`
  - Malformed JSON response → raise `BhashiniTTSError`

### FR-5: Custom Exception — `BhashiniTTSError`
- **What**: Custom exception class for all Bhashini TTS failures
- **Attributes**: `message` (str), optional `status_code` (int | None)
- **Usage**: Raised by `_call_bhashini()` on any failure. Caught by upper layers (S9.2, S9.5) for retry/degradation logic

### FR-6: Logging
- **What**: All Bhashini API calls logged via Loguru with `request_id`
- **Log points**:
  - INFO: Before call (language_code, text length — never log the actual text as it may contain medical info)
  - INFO: After successful call (response size in bytes, latency)
  - ERROR: On failure (status code, error type — never log response body which may contain audio)
- **Edge cases**: Ensure no PHI leaks into logs (no text content, no audio content)

---

## Tangible Outcomes

- [ ] **Outcome 1**: `from backend.app.services.tts import _call_bhashini, BhashiniTTSError` imports successfully
- [ ] **Outcome 2**: `_build_bhashini_payload("hello", "hi")` returns correct dict structure
- [ ] **Outcome 3**: `_call_bhashini()` with mocked httpx returns decoded audio bytes
- [ ] **Outcome 4**: `_call_bhashini()` raises `BhashiniTTSError` on HTTP errors, empty audio, timeouts
- [ ] **Outcome 5**: `_get_httpx_client()` returns singleton, `_reset_httpx_client()` clears it
- [ ] **Outcome 6**: Logging includes `request_id`, no PHI in logs

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

#### Module & Import Tests
1. **test_tts_module_importable**: `backend.app.services.tts` is importable
2. **test_bhashini_tts_error_importable**: `BhashiniTTSError` is importable and is an `Exception` subclass
3. **test_bhashini_tts_error_attributes**: Has `message` and `status_code` attributes
4. **test_call_bhashini_importable**: `_call_bhashini` is importable and is async

#### Constants Tests
5. **test_bhashini_inference_url_defined**: `BHASHINI_INFERENCE_URL` is a non-empty string starting with "https"
6. **test_bhashini_tts_gender_defined**: `BHASHINI_TTS_GENDER` equals `"female"`

#### Httpx Client Tests
7. **test_get_httpx_client_returns_async_client**: Returns `httpx.AsyncClient`
8. **test_get_httpx_client_singleton**: Two calls return same instance
9. **test_reset_httpx_client**: After reset, next call returns a new instance

#### Payload Builder Tests
10. **test_build_payload_structure**: Correct top-level keys (`pipelineTasks`, `inputData`)
11. **test_build_payload_language_code**: Language code appears at correct path
12. **test_build_payload_text**: Source text appears at correct path
13. **test_build_payload_gender**: Gender is "female"
14. **test_build_payload_task_type**: taskType is "tts"

#### _call_bhashini() Tests (mocked httpx)
15. **test_call_bhashini_happy_path**: Mocked 200 response with base64 audio → returns decoded bytes
16. **test_call_bhashini_sends_correct_headers**: Authorization and Content-Type headers present
17. **test_call_bhashini_sends_correct_payload**: POSTed JSON matches expected structure
18. **test_call_bhashini_http_error_raises**: 500 response → raises `BhashiniTTSError`
19. **test_call_bhashini_empty_audio_raises**: Response with empty `audioContent` → raises `BhashiniTTSError`
20. **test_call_bhashini_malformed_json_raises**: Non-JSON response → raises `BhashiniTTSError`
21. **test_call_bhashini_timeout_raises**: httpx.TimeoutException → raises `BhashiniTTSError`
22. **test_call_bhashini_missing_audio_key_raises**: Response JSON missing expected keys → raises `BhashiniTTSError`
23. **test_call_bhashini_logs_request_id**: Loguru log contains request_id
24. **test_call_bhashini_no_phi_in_logs**: Logs do not contain the input text or audio content

### Mocking Strategy
- **httpx**: Mock `httpx.AsyncClient.post()` — never make real HTTP calls
- **settings**: Mock `backend.app.core.config.settings` for `BHASHINI_API_KEY` and `BHASHINI_USER_ID`
- **Loguru**: Capture logs with `loguru` sink or mock `logger`

### Coverage Expectation
- All public and private functions tested
- All error paths covered (HTTP errors, empty responses, timeouts, malformed JSON)
- Zero PHI in test assertions or log captures

---

## References
- roadmap.md Phase 9
- Bhashini API docs: https://bhashini.gov.in/ulca/search-model (pipeline inference)
- design.md, requirements.md
