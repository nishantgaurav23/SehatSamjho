# Spec S5.3 — GPT-4O Vision Call

## Overview
Implements `_call_gpt4o_vision()`, the core async function that downloads a prescription image from its Twilio MediaUrl, base64-encodes it, and sends it to OpenAI's GPT-4O Vision model via `client.chat.completions.create()` with an `image_url` content block and the extraction system prompt from S5.2. Returns the raw JSON string from the model response. Model: `gpt-4o`. Max tokens: 1024.

## Dependencies
- **S5.1** — OpenAI async client init (`_get_client()`)
- **S5.2** — Extraction prompt (`_build_extraction_prompt()`, `EXTRACTION_SYSTEM_PROMPT`, `EXTRACTION_OUTPUT_SCHEMA`)

## Target Location
- `backend/app/services/extraction.py`

---

## Functional Requirements

### FR-1: `_download_image()` helper
- **What**: Async helper that downloads an image from a URL using httpx
- **Signature**: `async def _download_image(image_url: str) -> bytes`
- **Inputs**: `image_url` — HTTPS URL (Twilio MediaUrl)
- **Outputs**: Raw image bytes
- **Behaviour**:
  - Uses `httpx.AsyncClient` with a 30-second timeout
  - Sends an async GET request to the URL
  - Raises `httpx.HTTPStatusError` on non-2xx responses (via `response.raise_for_status()`)
  - Returns `response.content` (raw bytes)
- **Edge cases**:
  - Timeout: httpx raises `httpx.TimeoutException` (not caught here — propagated to caller)
  - Non-2xx: `raise_for_status()` raises `httpx.HTTPStatusError` (propagated)
  - Empty response body: returns empty bytes (caller validates)
- **Logging**: Log image download start and completion with `request_id` if available (debug level)

### FR-2: `_encode_image_base64()` helper
- **What**: Pure function that base64-encodes raw image bytes into a data URI string
- **Signature**: `def _encode_image_base64(image_bytes: bytes, content_type: str = "image/jpeg") -> str`
- **Inputs**:
  - `image_bytes` — raw image bytes from `_download_image()`
  - `content_type` — MIME type (default `"image/jpeg"`, also accepts `"image/png"`, `"image/webp"`)
- **Outputs**: A data URI string in the format `data:{content_type};base64,{encoded_data}`
- **Edge cases**:
  - Empty bytes: returns the data URI with empty base64 payload (caller validates)
  - Unknown content type: uses whatever is passed (no validation here)

### FR-3: `_call_gpt4o_vision()` main function
- **What**: Orchestrates the full GPT-4O Vision API call — download image, encode, build messages, call OpenAI
- **Signature**: `async def _call_gpt4o_vision(image_url: str, content_type: str = "image/jpeg") -> str`
- **Inputs**:
  - `image_url` — HTTPS URL of the prescription image
  - `content_type` — MIME type of the image (default `"image/jpeg"`)
- **Outputs**: Raw JSON string from GPT-4O response (the `message.content` text)
- **Behaviour**:
  1. Call `_download_image(image_url)` to get raw bytes
  2. Call `_encode_image_base64(image_bytes, content_type)` to get data URI
  3. Call `_build_extraction_prompt()` to get system messages
  4. Build user message with `image_url` content block:
     ```python
     {
         "role": "user",
         "content": [
             {
                 "type": "image_url",
                 "image_url": {"url": data_uri, "detail": "high"}
             },
             {
                 "type": "text",
                 "text": "Extract all medical information from this prescription image."
             }
         ]
     }
     ```
  5. Call `_get_client().chat.completions.create()` with:
     - `model="gpt-4o"`
     - `messages=system_messages + [user_message]`
     - `max_tokens=1024`
     - `temperature=0.1` (low for deterministic extraction)
  6. Return `response.choices[0].message.content`
- **Edge cases**:
  - OpenAI API errors: propagated to caller (S5.5 handles retry)
  - Empty response content: return empty string (caller validates)
  - No choices in response: raise `ValueError("GPT-4O returned no choices")`
- **Logging**:
  - Debug: log before API call with model name
  - Debug: log after API call with token usage (prompt_tokens, completion_tokens)
  - Never log image bytes or base64 content (PHI risk)

### FR-4: Model and token configuration
- **What**: Module-level constants for GPT-4O call parameters
- **Constants**:
  - `GPT4O_MODEL: str = "gpt-4o"` — model identifier
  - `GPT4O_MAX_TOKENS: int = 1024` — max completion tokens
  - `GPT4O_TEMPERATURE: float = 0.1` — low temperature for extraction
  - `GPT4O_IMAGE_DETAIL: str = "high"` — image detail level for Vision API
- **Rationale**: Centralised constants make tuning and testing easier

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_download_image()` is an async function in `extraction.py` that returns bytes
- [ ] **Outcome 2**: `_encode_image_base64()` is a pure function that returns a valid data URI string
- [ ] **Outcome 3**: `_call_gpt4o_vision()` is an async function that returns a raw JSON string
- [ ] **Outcome 4**: `GPT4O_MODEL`, `GPT4O_MAX_TOKENS`, `GPT4O_TEMPERATURE`, `GPT4O_IMAGE_DETAIL` constants exist
- [ ] **Outcome 5**: The OpenAI API call uses `model="gpt-4o"` and `max_tokens=1024`
- [ ] **Outcome 6**: The user message includes an `image_url` content block with `detail="high"`
- [ ] **Outcome 7**: The user message includes a text content block with extraction instruction
- [ ] **Outcome 8**: System prompt from `_build_extraction_prompt()` is included in messages
- [ ] **Outcome 9**: Token usage is logged at debug level after the API call
- [ ] **Outcome 10**: No image bytes or base64 content is ever logged (PHI safety)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

**Constants tests (pure, no mocking):**
1. **test_gpt4o_model_constant**: `GPT4O_MODEL` equals `"gpt-4o"`
2. **test_gpt4o_max_tokens_constant**: `GPT4O_MAX_TOKENS` equals `1024`
3. **test_gpt4o_temperature_constant**: `GPT4O_TEMPERATURE` equals `0.1`
4. **test_gpt4o_image_detail_constant**: `GPT4O_IMAGE_DETAIL` equals `"high"`

**`_encode_image_base64()` tests (pure, no mocking):**
5. **test_encode_image_base64_returns_string**: returns a `str`
6. **test_encode_image_base64_default_content_type**: output starts with `data:image/jpeg;base64,`
7. **test_encode_image_base64_custom_content_type**: passing `image/png` produces `data:image/png;base64,`
8. **test_encode_image_base64_correct_encoding**: base64-decoding the payload matches original bytes
9. **test_encode_image_base64_empty_bytes**: returns data URI with empty payload for empty input

**`_download_image()` tests (mock httpx):**
10. **test_download_image_success**: mocked httpx returns 200 with bytes — function returns those bytes
11. **test_download_image_raises_on_non_2xx**: mocked httpx returns 404 — raises `httpx.HTTPStatusError`
12. **test_download_image_timeout**: mocked httpx raises `httpx.TimeoutException` — propagated
13. **test_download_image_uses_async_client**: verifies `httpx.AsyncClient` is used (not sync)

**`_call_gpt4o_vision()` tests (mock _download_image, _get_client):**
14. **test_call_gpt4o_vision_returns_string**: returns a string from mocked response
15. **test_call_gpt4o_vision_calls_download**: verifies `_download_image` is called with the image URL
16. **test_call_gpt4o_vision_calls_openai**: verifies `client.chat.completions.create` is called
17. **test_call_gpt4o_vision_model_param**: OpenAI call uses `model="gpt-4o"`
18. **test_call_gpt4o_vision_max_tokens_param**: OpenAI call uses `max_tokens=1024`
19. **test_call_gpt4o_vision_temperature_param**: OpenAI call uses `temperature=0.1`
20. **test_call_gpt4o_vision_messages_structure**: messages list has system message + user message with image_url block
21. **test_call_gpt4o_vision_image_detail_high**: image_url block has `detail="high"`
22. **test_call_gpt4o_vision_user_text_block**: user message includes text content block
23. **test_call_gpt4o_vision_no_choices_raises**: response with empty `choices` raises `ValueError`
24. **test_call_gpt4o_vision_content_type_forwarded**: custom content_type is passed to `_encode_image_base64`

### Mocking Strategy
- **httpx**: Mock `httpx.AsyncClient` for `_download_image()` tests
- **OpenAI client**: Mock `_get_client()` to return a mock `AsyncOpenAI` whose `chat.completions.create` returns a fake `ChatCompletion` response
- **_download_image**: Mock at module level for `_call_gpt4o_vision()` tests to isolate from network I/O
- **Never mock**: `_encode_image_base64()` (pure function), constants

### Coverage Expectation
- All public and private functions have at least one test; edge cases covered
- 24 tests total

---

## References
- `roadmap.md` — S5.3 row (Phase 5, GPT-4O Vision Extraction)
- `backend/app/models/schemas.py` — `PrescriptionData`, `MedicineEntry` definitions
- `backend/app/services/extraction.py` — existing S5.1 + S5.2 code
- [OpenAI Vision API docs](https://platform.openai.com/docs/guides/vision) — image_url content block format
