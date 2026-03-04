# Spec S9.2 — text_to_speech()

## Overview
Public-facing function that converts translated text into speech audio bytes using the Bhashini TTS client from S9.1. Validates inputs (text non-empty, language code supported), calls `_call_bhashini()`, validates the returned audio bytes (non-empty, reasonable size <=10MB), and applies tenacity retry logic on transient `BhashiniTTSError` failures. This is the primary entry point consumed by S9.3 (S3 upload) and S9.4 (audio delivery orchestrator).

## Dependencies
- S9.1 (Bhashini TTS API client) — `_call_bhashini()`, `BhashiniTTSError`

## Target Location
- `backend/app/services/tts.py`

---

## Functional Requirements

### FR-1: `text_to_speech()` Function Signature
- **What**: Async function `text_to_speech(text: str, language_code: str, request_id: str = "") -> bytes`
- **Inputs**:
  - `text`: The translated text to convert to speech
  - `language_code`: ISO 639-1 language code (e.g. "hi", "ta")
  - `request_id`: Optional correlation ID for logging
- **Outputs**: Raw audio `bytes` from Bhashini TTS
- **Edge cases**: Empty text, unsupported language code, extremely long text

### FR-2: Input Validation
- **What**: Validate inputs before calling Bhashini
- **Rules**:
  - `text` must be a non-empty string (after stripping whitespace) — raise `ValueError` if empty
  - `language_code` must be a non-empty string — raise `ValueError` if empty
- **Edge cases**: Whitespace-only text, None-like values

### FR-3: Audio Size Validation
- **What**: After receiving audio bytes from `_call_bhashini()`, validate size
- **Rules**:
  - Audio bytes must be non-empty (>0 bytes) — raise `BhashiniTTSError` if empty
  - Audio bytes must not exceed `MAX_AUDIO_SIZE` (10 MB = 10 * 1024 * 1024 bytes) — raise `BhashiniTTSError` if too large
- **Constants**: `MAX_AUDIO_SIZE = 10 * 1024 * 1024`
- **Edge cases**: Exactly at limit (should pass), 1 byte over (should fail)

### FR-4: Tenacity Retry on Transient Errors
- **What**: Wrap `text_to_speech()` with tenacity `@retry` for transient `BhashiniTTSError` failures
- **Config**:
  - `retry=retry_if_exception_type(BhashiniTTSError)` — only retry Bhashini errors, NOT `ValueError`
  - `stop=stop_after_attempt(3)` — max 3 attempts
  - `wait=wait_exponential(multiplier=1, min=1, max=10)` — exponential backoff
  - `reraise=True` — re-raise the original exception after exhausting retries
- **Edge cases**: `ValueError` must NOT be retried (input validation failures are permanent)

### FR-5: Logging
- **What**: Log key events with `request_id` via Loguru
- **Log points**:
  - INFO: Before calling Bhashini (language_code, text_length — never log text content)
  - INFO: After successful call (audio size in bytes)
  - WARNING: On retry attempt (attempt number, error message)
  - ERROR: On final failure after retries exhausted
- **Edge cases**: Ensure no PHI in logs — never log the text content or audio bytes

---

## Tangible Outcomes

- [ ] **Outcome 1**: `from backend.app.services.tts import text_to_speech` imports successfully
- [ ] **Outcome 2**: `text_to_speech()` is async and has correct signature (text, language_code, request_id)
- [ ] **Outcome 3**: Valid inputs → calls `_call_bhashini()` → returns audio bytes
- [ ] **Outcome 4**: Empty/whitespace text raises `ValueError` (not retried)
- [ ] **Outcome 5**: Empty language_code raises `ValueError` (not retried)
- [ ] **Outcome 6**: Audio bytes exceeding `MAX_AUDIO_SIZE` raises `BhashiniTTSError`
- [ ] **Outcome 7**: `BhashiniTTSError` from `_call_bhashini()` is retried up to 3 times
- [ ] **Outcome 8**: `MAX_AUDIO_SIZE` constant equals 10 * 1024 * 1024
- [ ] **Outcome 9**: Logging includes `request_id`, no PHI in logs

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

#### Import & Signature Tests
1. **test_text_to_speech_importable**: `text_to_speech` is importable from `backend.app.services.tts`
2. **test_text_to_speech_is_async**: `text_to_speech` is a coroutine function
3. **test_text_to_speech_signature**: Accepts `text`, `language_code`, `request_id` params
4. **test_max_audio_size_constant**: `MAX_AUDIO_SIZE` equals `10 * 1024 * 1024`

#### Input Validation Tests
5. **test_empty_text_raises_value_error**: `text_to_speech("", "hi")` raises `ValueError`
6. **test_whitespace_text_raises_value_error**: `text_to_speech("   ", "hi")` raises `ValueError`
7. **test_empty_language_code_raises_value_error**: `text_to_speech("hello", "")` raises `ValueError`

#### Happy Path Tests (mocked _call_bhashini)
8. **test_happy_path_returns_audio_bytes**: Valid inputs → returns bytes from `_call_bhashini()`
9. **test_calls_bhashini_with_correct_args**: `_call_bhashini()` called with text, language_code, request_id
10. **test_passes_request_id_to_bhashini**: request_id forwarded to `_call_bhashini()`
11. **test_returns_bytes_type**: Return type is `bytes`

#### Audio Validation Tests
12. **test_empty_audio_raises_bhashini_error**: `_call_bhashini()` returns `b""` → raises `BhashiniTTSError`
13. **test_oversized_audio_raises_bhashini_error**: Audio > MAX_AUDIO_SIZE → raises `BhashiniTTSError`
14. **test_audio_at_max_size_passes**: Audio exactly MAX_AUDIO_SIZE → passes (no error)

#### Retry Tests
15. **test_retries_on_bhashini_tts_error**: `BhashiniTTSError` triggers retry (up to 3 attempts)
16. **test_no_retry_on_value_error**: `ValueError` is NOT retried
17. **test_retry_succeeds_on_second_attempt**: First call fails, second succeeds → returns audio
18. **test_retry_exhausted_raises_original**: 3 failures → raises `BhashiniTTSError`
19. **test_retry_exponential_backoff**: Uses exponential wait strategy

#### Logging Tests
20. **test_logs_request_id**: Log output contains `request_id`
21. **test_no_phi_in_logs**: Logs do not contain the input text content
22. **test_logs_audio_size_on_success**: Successful call logs audio byte count

### Mocking Strategy
- **_call_bhashini**: Mock `backend.app.services.tts._call_bhashini` — never make real HTTP calls
- **Loguru**: Capture logs with `loguru` sink or mock `logger`
- **tenacity**: For retry tests, mock `_call_bhashini` with side_effect lists

### Coverage Expectation
- All public functions have at least one test
- All error paths covered (empty text, empty lang, empty audio, oversized audio, retries)
- Zero PHI in test assertions or log captures

---

## References
- roadmap.md Phase 9
- S9.1 spec (Bhashini TTS API client)
- Bhashini API docs: https://bhashini.gov.in/ulca/search-model
