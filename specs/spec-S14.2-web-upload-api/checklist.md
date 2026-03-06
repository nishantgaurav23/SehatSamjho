# S14.2 — Web Upload API — Checklist

- [x] FR-1: Create `backend/app/api/web.py` with APIRouter
- [x] FR-1: Register router in `main.py` at `/api`
- [x] FR-2: `POST /api/translate` endpoint (UploadFile + language_code)
- [x] FR-2: Input validation (image type, size, language_code)
- [x] FR-3: Pipeline execution (extract -> enrich -> glossary -> translate -> TTS)
- [x] FR-4: `WebTranslationResponse` + `WebMedicineDetail` Pydantic models in schemas.py
- [x] FR-4: JSON response with medicines, translation, audio_url
- [x] FR-5: Error handling (422 for semantic, 500 for transient)
- [x] FR-6: CORS middleware added to app
- [x] FR-7: `extract_prescription_from_bytes()` for direct image bytes
- [ ] Tests: 20 tests (deferred to S14.4)
