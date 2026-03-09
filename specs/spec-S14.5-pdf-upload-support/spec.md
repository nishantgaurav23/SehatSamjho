# S14.5 — PDF Upload Support

## Context
The web upload API (S14.2) currently only accepts image files (JPEG, PNG). Many Indian prescriptions and lab reports are shared as PDF files — scanned documents, hospital discharge summaries, pathology reports, etc. This spec adds PDF support by converting PDF pages to images before feeding them into the existing GPT-4O Vision extraction pipeline.

## Dependencies
- S14.2 (Web upload API — `POST /api/translate`)
- S14.3 (Web frontend — file upload UI)
- S5.4 (extract_prescription / extract_prescription_from_bytes)

## Functional Requirements

### FR-1: PDF conversion service
- Create `backend/app/services/pdf_converter.py`.
- Function: `async def convert_pdf_to_images(pdf_bytes: bytes, *, max_pages: int = 5, dpi: int = 200) -> list[bytes]`
  - Accepts raw PDF bytes.
  - Converts each page to a JPEG image (RGB, quality 90).
  - Returns a list of image byte arrays (one per page).
  - Limits to first `max_pages` pages (default 5) to bound cost/latency.
  - Raises `PdfConversionError` if conversion fails (corrupt PDF, password-protected, etc.).
  - Uses `PyMuPDF` (`fitz`) library — pure Python, no system dependency (unlike `pdf2image` which requires `poppler`).
- Function: `def is_pdf(content_type: str, file_bytes: bytes) -> bool`
  - Returns `True` if content_type is `application/pdf` OR file_bytes starts with `%PDF` magic bytes.
  - Handles edge cases: missing content_type, empty bytes.

### FR-2: Multi-page extraction strategy
- Function: `async def extract_from_pdf(pdf_bytes: bytes, *, request_id: str) -> PrescriptionData`
  - Converts PDF to images via `convert_pdf_to_images()`.
  - Extracts each page via `extract_prescription_from_bytes()`.
  - Merges results: union of all medicines/lab_tests, highest confidence wins for shared fields (doctor_name, diagnosis, date, doc_type).
  - If only 1 page, return its result directly (no merge overhead).
  - If all pages return `doc_type="other"`, raise `NotMedicalDocumentError`.
  - Logs page count and per-page latency for observability.

### FR-3: Update web upload API
- Update `backend/app/api/web.py`:
  - Accept both `image/*` and `application/pdf` content types.
  - Rename `image` form field to `file` (backward-compatible: also accept `image` field name).
  - For PDF files: call `extract_from_pdf()` instead of `extract_prescription_from_bytes()`.
  - For image files: existing flow unchanged.
  - Max file size remains 10MB.
  - Add `page_count` field to `WebTranslationResponse` (optional int, null for images).

### FR-4: Update web frontend
- Update `backend/templates/index.html`:
  - Change file input `accept` attribute: `accept="image/*,.pdf,application/pdf"`.
- Update `backend/static/app.js`:
  - Update `handleFileSelect()` validation: accept `file.type.startsWith("image/")` OR `file.type === "application/pdf"`.
  - For PDF files: show a PDF icon placeholder instead of image preview.
  - Update form submission: use field name `file` (keep `image` as fallback).
- Update `backend/static/i18n.js`:
  - Update `err_not_image` key to `err_not_supported` across all 22 languages: "Please select an image (JPEG, PNG) or PDF file."
  - Add `upload_pdf_preview` key: "PDF document selected" (all 22 languages).
  - Update `upload_hint` to mention PDF: "Drag & drop your prescription photo or PDF here..."

### FR-5: Update error handling
- Add `PdfConversionError` exception class in `pdf_converter.py`.
- Map in `web.py` error handler: `PdfConversionError` → HTTP 422 `{"detail": "pdf_conversion_error"}`.
- Add `err_pdf_error` i18n key: "Could not read this PDF. Please try a clearer scan or photo instead."
- Add `err_pdf_too_many_pages` i18n key: "PDF has too many pages. Maximum 5 pages supported."

## Non-Functional Requirements

### NFR-1: Performance
- PDF conversion should complete in < 3 seconds for a 5-page PDF on EC2 t3.micro.
- Memory usage: PyMuPDF processes pages one at a time to avoid loading entire PDF into memory.
- JPEG quality 90 balances extraction accuracy with size.

### NFR-2: Security
- Validate PDF magic bytes (`%PDF`) to prevent content-type spoofing.
- Do not store PDF contents — process in memory, discard after extraction.
- Zero PHI: no PDF content logged, only metadata (page count, file size, latency).

### NFR-3: Dependencies
- Add `PyMuPDF>=1.24.0` to `pyproject.toml` runtime dependencies.
- PyMuPDF is a pure wheel (no system deps like poppler), works on EC2 t3.micro.

## Files Changed
| File | Change |
|------|--------|
| `pyproject.toml` | Add `PyMuPDF>=1.24.0` dependency |
| `backend/app/services/pdf_converter.py` | **New** — `convert_pdf_to_images()`, `extract_from_pdf()`, `is_pdf()`, `PdfConversionError` |
| `backend/app/api/web.py` | Accept PDF, route to `extract_from_pdf()` |
| `backend/app/models/schemas.py` | Add `page_count: int | None` to `WebTranslationResponse` |
| `backend/templates/index.html` | Update file input accept attribute |
| `backend/static/app.js` | PDF validation, PDF preview icon, field name update |
| `backend/static/i18n.js` | Update error messages, add PDF-related keys |

## Test Plan (20 tests)

### Unit Tests: `backend/tests/services/test_pdf_converter.py`
1. **test_import** — `pdf_converter` module importable
2. **test_convert_pdf_to_images_signature** — accepts `(pdf_bytes, *, max_pages, dpi)`, returns `list[bytes]`
3. **test_is_pdf_with_pdf_content_type** — `is_pdf("application/pdf", b"")` returns True
4. **test_is_pdf_with_magic_bytes** — `is_pdf("", b"%PDF-1.4...")` returns True
5. **test_is_pdf_with_image** — `is_pdf("image/jpeg", b"\xff\xd8...")` returns False
6. **test_convert_single_page_pdf** — 1-page PDF → list with 1 JPEG bytes
7. **test_convert_multi_page_pdf** — 3-page PDF → list with 3 JPEG bytes
8. **test_convert_respects_max_pages** — 10-page PDF with max_pages=2 → list with 2 items
9. **test_convert_corrupt_pdf_raises** — corrupt bytes → `PdfConversionError`
10. **test_convert_empty_pdf_raises** — empty bytes → `PdfConversionError`
11. **test_convert_password_protected_raises** — password-protected PDF → `PdfConversionError`
12. **test_output_is_valid_jpeg** — output bytes start with JPEG magic `\xff\xd8\xff`
13. **test_extract_from_pdf_single_page** — calls `extract_prescription_from_bytes` once, returns result
14. **test_extract_from_pdf_multi_page_merges** — 2 pages with different medicines → merged list
15. **test_extract_from_pdf_all_other_raises** — all pages `doc_type="other"` → `NotMedicalDocumentError`
16. **test_extract_from_pdf_highest_confidence** — picks highest confidence for shared fields
17. **test_extract_from_pdf_logs_page_count** — loguru output includes page count
18. **test_pdf_conversion_error_class** — `PdfConversionError` is subclass of `Exception`

### API Tests: `backend/tests/api/test_web_pdf.py`
19. **test_web_translate_accepts_pdf** — POST with PDF → 200, valid response with `page_count`
20. **test_web_translate_rejects_unsupported** — POST with `.docx` → 400

## Acceptance Criteria
- [ ] `PyMuPDF` added to pyproject.toml and installable via `uv pip install -r pyproject.toml`
- [ ] `POST /api/translate` accepts both image/* and application/pdf
- [ ] Single-page PDF extracts correctly
- [ ] Multi-page PDF (up to 5 pages) extracts and merges correctly
- [ ] PDF > 5 pages processes only first 5 pages
- [ ] Corrupt/password-protected PDFs return clear error message
- [ ] Frontend accepts PDF files in drag-drop and file picker
- [ ] PDF preview shows document icon (not broken image)
- [ ] All error messages translated to 22 languages
- [ ] 20/20 tests pass
- [ ] Zero PHI logged
