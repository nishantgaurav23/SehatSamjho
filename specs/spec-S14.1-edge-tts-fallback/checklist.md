# S14.1 — Edge TTS Fallback — Checklist

- [x] FR-1: Add `edge-tts>=6.1` to pyproject.toml
- [x] FR-2: EDGE_TTS_VOICES mapping (10 Indian languages)
- [x] FR-3: `edge_text_to_speech()` async function
- [x] FR-3: EdgeTTSError custom exception
- [x] FR-4: Provider selection in `generate_and_deliver_audio()` via `_get_audio_bytes()`
- [x] FR-4: Bhashini-first, Edge TTS fallback logic
- [x] FR-4: S3 upload with correct extension (.mp3 vs .ogg)
- [x] FR-5: Existing Bhashini code unchanged
- [x] Tests: 22 tests passing (test_tts_edge.py)
- [x] Existing S9 tests updated and passing (84 TTS tests total)
