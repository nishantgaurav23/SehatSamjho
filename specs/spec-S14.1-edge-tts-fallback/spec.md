# S14.1 — Edge TTS Fallback Provider

## Context
Bhashini TTS requires an API key that is not yet available. We need an alternative TTS provider that supports Indian languages, works without an API key, and can be used immediately. `edge-tts` (Microsoft Edge's neural TTS) is free, async-compatible, and supports 10+ Indian languages.

## Dependencies
- S9.1 (Bhashini TTS client)
- S9.4 (Audio delivery orchestrator)
- S1.1 (pyproject.toml)

## Functional Requirements

### FR-1: Add `edge-tts` dependency
- Add `edge-tts>=6.1` to `pyproject.toml` runtime dependencies.

### FR-2: Edge TTS language voice mapping
- Create `backend/app/services/tts_edge.py`.
- Define `EDGE_TTS_VOICES: dict[str, str]` mapping language codes to Microsoft Edge voice names.
- Supported Indian languages: hi, bn, ta, te, mr, gu, kn, ml, pa, ur (at minimum).
- Each voice should use the neural female variant for consistency with Bhashini.
- Unsupported languages return `None` (graceful skip).

### FR-3: `edge_text_to_speech(text, language_code, request_id)` function
- Async function that converts text to audio bytes using `edge-tts`.
- Returns `bytes` (MP3 audio).
- Raises `EdgeTTSError` on failure (custom exception in same module).
- Logs request_id, language_code, text_length, latency.

### FR-4: TTS provider selection in `generate_and_deliver_audio()`
- Modify `backend/app/services/tts.py` -> `generate_and_deliver_audio()`.
- Try Bhashini first (if `BHASHINI_API_KEY` is set and non-empty).
- If Bhashini is unavailable (no key) or fails, fall back to Edge TTS.
- If Edge TTS also fails, return `None` (existing graceful degradation).
- S3 upload uses `.mp3` extension when Edge TTS is the source (not `.ogg`).

### FR-5: No changes to existing Bhashini code
- All existing Bhashini TTS code remains untouched.
- Edge TTS is purely additive.

## Non-Functional Requirements
- Edge TTS calls should have a 30-second timeout.
- Retry via tenacity (2 attempts) on transient errors.
- Zero PHI in logs (same as Bhashini).

## Test Plan
- 20 tests in `backend/tests/services/test_tts_edge.py`.
- Test voice mapping, text_to_speech, error handling, provider selection fallback.
- All edge-tts calls mocked (no network in tests).
