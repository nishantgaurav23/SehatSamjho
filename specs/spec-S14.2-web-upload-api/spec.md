# S14.2 — Web Upload API Endpoint

## Context
The current pipeline is only accessible via WhatsApp/Twilio webhook. We need an HTTP API endpoint that accepts a prescription image upload + language selection and returns the translated results as JSON — powering the web frontend (S14.3).

## Dependencies
- S5.4 (extract_prescription)
- S8.4 (enrich_prescription)
- S6.3 (lookup_terms)
- S6.4 (format_glossary_context)
- S7.4 (simplify_and_translate)
- S14.1 (Edge TTS fallback)
- S9.4 (generate_and_deliver_audio)

## Functional Requirements

### FR-1: New API router
- Create `backend/app/api/web.py` with an `APIRouter` at prefix `/api`.
- Register in `main.py` via `app.include_router()`.

### FR-2: `POST /api/translate` endpoint
- Accepts `multipart/form-data`:
  - `image`: UploadFile (required) — prescription image (JPEG, PNG)
  - `language_code`: str (required) — one of the 22 supported language codes
- Validates:
  - Image content type must start with `image/`
  - Image size <= 10MB
  - language_code must be in SUPPORTED_LANGUAGES
- Returns 400 on validation failure with descriptive error.

### FR-3: Pipeline execution
- Generate request_id (UUID4).
- Save uploaded image to a temp file (or use in-memory bytes).
- Run the same pipeline as WhatsApp:
  1. `extract_prescription()` — pass image bytes directly (base64 encode in-memory, no URL download needed)
  2. `enrich_prescription()` — drug lookup
  3. `lookup_terms()` + `format_glossary_context()` — glossary
  4. `simplify_and_translate()` — Claude translation
  5. `generate_and_deliver_audio()` — TTS (Edge TTS fallback)
- No Twilio, no WhatsApp, no Redis session needed.

### FR-4: Response schema
- Return JSON:
```json
{
  "request_id": "uuid",
  "language": {"code": "hi", "name": "Hindi"},
  "medicines": [
    {
      "name": "Amoxicillin",
      "dosage": "500mg",
      "frequency": "twice daily",
      "duration": "5 days",
      "confidence": 0.95,
      "purpose": "Antibiotic for bacterial infections",
      "side_effects": "Nausea, diarrhea"
    }
  ],
  "translated_text": "...",
  "per_medicine_summaries": ["..."],
  "disclaimer": "...",
  "audio_url": "https://s3...presigned" | null,
  "latency_ms": 12345
}
```
- Pydantic response model: `WebTranslationResponse` in `schemas.py`.

### FR-5: Error handling
- Map pipeline exceptions to HTTP status codes:
  - `NotMedicalDocumentError` -> 422 with message
  - `ImageNotReadableError` -> 422 with message
  - `TranslationError` / `ExtractionError` -> 500 with message
  - Generic -> 500
- Never expose stack traces or PHI.

### FR-6: CORS
- Add `CORSMiddleware` to the app (allow all origins for prototype).

### FR-7: Extract from bytes (no URL download)
- The web endpoint receives image bytes directly (not a Twilio media URL).
- Add a `extract_prescription_from_bytes()` variant or adapt `extract_prescription()` to accept raw bytes in addition to URLs.

## Non-Functional Requirements
- No authentication required for prototype.
- Request logging with request_id via Loguru.
- No DB logging for web requests (optional future enhancement).

## Test Plan
- 20 tests in `backend/tests/api/test_web_upload.py`.
- Test: validation, pipeline execution, response schema, error mapping, CORS.
- All external services mocked.
