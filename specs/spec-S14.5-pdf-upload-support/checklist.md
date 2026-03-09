# S14.5 — PDF Upload Support — Checklist

## Dependencies
- [x] S14.2 (Web upload API)
- [x] S14.3 (Web frontend)
- [x] S5.4 (extract_prescription)

## Implementation

### Phase 1: Dependency + PDF Converter Service
- [x] Add `PyMuPDF>=1.24.0` to `pyproject.toml`
- [x] Install: `uv pip install -r pyproject.toml`
- [x] Create `backend/app/services/pdf_converter.py`
  - [x] `PdfConversionError` exception class
  - [x] `is_pdf(content_type, file_bytes)` function
  - [x] `convert_pdf_to_images(pdf_bytes, *, max_pages=5, dpi=200)` function
  - [x] `extract_from_pdf(pdf_bytes, *, request_id)` function

### Phase 2: Backend API Update
- [x] Update `backend/app/api/web.py` — accept PDF content type
- [x] Route PDF to `extract_from_pdf()`
- [x] Add `PdfConversionError` → HTTP 422 mapping
- [x] Add `page_count` to `WebTranslationResponse` schema

### Phase 3: Frontend Update
- [x] Update `index.html` file input accept attribute
- [x] Update `app.js` file validation for PDF
- [x] Add PDF preview icon in upload zone
- [x] Update `i18n.js` error messages for PDF

### Phase 4: Tests
- [x] Write `backend/tests/services/test_pdf_converter.py` (18 tests)
- [x] Write `backend/tests/api/test_web_pdf.py` (2 tests)
- [x] All 20 tests pass

## Verification
- [x] `uv pip install -r pyproject.toml` succeeds
- [x] `POST /api/translate` with PDF → 200
- [x] `POST /api/translate` with image → 200 (no regression)
- [x] Frontend drag-drop works for PDF
- [x] Ruff lint passes
- [x] Total test count updated
