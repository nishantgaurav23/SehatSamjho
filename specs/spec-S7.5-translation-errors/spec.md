# Spec S7.5 — Retry + Error Handling (Translation)

## Overview
Adds Tenacity retry logic on transient Anthropic API errors (3 attempts, exponential backoff) to `simplify_and_translate()`, and introduces a `TranslationError` custom exception raised on parse failures or empty responses. All errors are logged with `request_id` and `language_code`. Follows the same pattern established by S5.5 for extraction errors.

## Dependencies
- **S7.4** — `simplify_and_translate()` (the function being wrapped with retry + error handling)

## Target Location
`backend/app/services/translation.py`

---

## Functional Requirements

### FR-1: TranslationError exception class
- **What**: A custom `TranslationError(Exception)` base class for all translation-related errors.
- **Inputs**: Standard exception args (message string)
- **Outputs**: Raisable exception
- **Edge cases**: Must be importable from the module, must be a subclass of `Exception`

### FR-2: Tenacity retry decorator on simplify_and_translate
- **What**: Wrap `simplify_and_translate()` with `@retry` from tenacity:
  - `stop=stop_after_attempt(3)` — max 3 attempts
  - `wait=wait_exponential(multiplier=1, min=2, max=10)` — exponential backoff
  - `retry=retry_if_exception_type(...)` — only retry transient Anthropic errors:
    - `anthropic.APITimeoutError`
    - `anthropic.APIConnectionError`
    - `anthropic.RateLimitError`
    - `anthropic.InternalServerError`
  - `reraise=True` — re-raise after final attempt
- **Inputs**: Same function signature as S7.4
- **Outputs**: Same return type, but with automatic retry on transient errors
- **Edge cases**: Non-retryable errors (AuthenticationError, BadRequestError) propagate immediately without retry

### FR-3: Retry logging callback
- **What**: A `_log_translation_retry()` callback used as `before_sleep` in the retry decorator. Logs each retry attempt with `attempt_number`, `wait_time`, and error representation. PHI-safe — never logs prompt content.
- **Inputs**: tenacity `RetryCallState`
- **Outputs**: Log entry (loguru warning)

### FR-4: TranslationError on empty/malformed response
- **What**: Replace the existing `ValueError` raised on empty response with `TranslationError`. Also raise `TranslationError` if `response.content[0].text` is empty or whitespace-only after extraction.
- **Inputs**: Claude API response
- **Outputs**: `TranslationError` raised with descriptive message
- **Edge cases**: Empty content list, whitespace-only text, `None` text attribute

### FR-5: Error logging with request_id and language_code
- **What**: All error paths log with both `request_id` and `language_code` for correlation. Transient errors logged at WARNING (via retry callback). Final failures logged at ERROR.
- **Inputs**: request_id, language_code, exception details
- **Outputs**: Structured log entries
- **Edge cases**: Empty request_id (still logged), PHI-safe (no prompt/response content in logs)

### FR-6: Non-retryable Anthropic errors propagate immediately
- **What**: Errors like `anthropic.AuthenticationError` and `anthropic.BadRequestError` are NOT retried — they propagate immediately as-is (not wrapped in TranslationError).
- **Inputs**: Non-transient Anthropic exception
- **Outputs**: Original exception re-raised without retry

---

## Tangible Outcomes

- [ ] **Outcome 1**: `TranslationError` is importable from `backend.app.services.translation`
- [ ] **Outcome 2**: `TranslationError` is a subclass of `Exception`
- [ ] **Outcome 3**: `simplify_and_translate` has tenacity `@retry` decorator
- [ ] **Outcome 4**: Retries up to 3 times on `APITimeoutError`, `APIConnectionError`, `RateLimitError`, `InternalServerError`
- [ ] **Outcome 5**: Does NOT retry on `AuthenticationError` or `BadRequestError`
- [ ] **Outcome 6**: Raises `TranslationError` (not `ValueError`) on empty response
- [ ] **Outcome 7**: `_log_translation_retry` logs attempt number and wait time
- [ ] **Outcome 8**: All error logs include request_id, never contain PHI

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

**Exception Class (3 tests)**
1. **test_import_translation_error**: TranslationError importable from module
2. **test_translation_error_is_exception**: Subclass of Exception
3. **test_translation_error_message**: Stores and returns message string

**Retry Decorator (5 tests)**
4. **test_retry_on_api_timeout_error**: Retries on anthropic.APITimeoutError
5. **test_retry_on_api_connection_error**: Retries on anthropic.APIConnectionError
6. **test_retry_on_rate_limit_error**: Retries on anthropic.RateLimitError
7. **test_retry_on_internal_server_error**: Retries on anthropic.InternalServerError
8. **test_max_3_attempts**: Stops after 3 attempts and re-raises

**Non-Retryable Errors (2 tests)**
9. **test_no_retry_on_authentication_error**: AuthenticationError propagates immediately (1 call)
10. **test_no_retry_on_bad_request_error**: BadRequestError propagates immediately (1 call)

**TranslationError Raising (3 tests)**
11. **test_empty_response_raises_translation_error**: Empty content raises TranslationError
12. **test_whitespace_response_raises_translation_error**: Whitespace-only text raises TranslationError
13. **test_translation_error_includes_request_id**: Error message or log includes request_id

**Retry Logging (4 tests)**
14. **test_log_translation_retry_exists**: _log_translation_retry is callable
15. **test_retry_callback_logs_attempt**: Logs attempt number
16. **test_retry_callback_logs_wait_time**: Logs wait/sleep time
17. **test_retry_logs_never_contain_phi**: Retry logs don't contain prompt/response content

**Integration (3 tests)**
18. **test_succeeds_after_transient_failure**: Fails once then succeeds on retry
19. **test_raises_after_all_retries_exhausted**: 3 failures → re-raises original error
20. **test_error_log_includes_language_code**: Error log includes language_code

### Mocking Strategy
- `_get_client()` — mock to return a mock `AsyncAnthropic` client
- `client.messages.create()` — `AsyncMock` that raises various Anthropic exceptions
- Tenacity — set `wait=wait_none()` in tests to skip actual backoff delays
- Loguru — capture with `StringIO` sink

### Coverage Expectation
- All public functions/classes have at least one test; edge cases covered
- 20 tests total
