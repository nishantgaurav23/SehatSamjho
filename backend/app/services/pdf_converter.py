"""S14.5 — PDF Upload Support.

Converts PDF documents to images for prescription extraction via GPT-4O Vision.
Uses PyMuPDF (fitz) — pure wheel, no system dependencies.
"""

from __future__ import annotations

import time

import fitz
from loguru import logger


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class PdfConversionError(Exception):
    """Raised when PDF conversion fails (corrupt, password-protected, etc.)."""


# ---------------------------------------------------------------------------
# is_pdf()
# ---------------------------------------------------------------------------


def is_pdf(content_type: str, file_bytes: bytes) -> bool:
    """Check if the file is a PDF by content type or magic bytes.

    Returns True if content_type is 'application/pdf' OR file_bytes starts with '%PDF'.
    """
    if content_type == "application/pdf":
        return True
    if file_bytes and file_bytes[:4] == b"%PDF":
        return True
    return False


# ---------------------------------------------------------------------------
# convert_pdf_to_images()
# ---------------------------------------------------------------------------


async def convert_pdf_to_images(
    pdf_bytes: bytes,
    *,
    max_pages: int = 5,
    dpi: int = 200,
) -> list[bytes]:
    """Convert PDF pages to JPEG images.

    Args:
        pdf_bytes: Raw PDF file bytes.
        max_pages: Maximum number of pages to convert (default 5).
        dpi: Resolution for rendering (default 200).

    Returns:
        List of JPEG bytes, one per page.

    Raises:
        PdfConversionError: If PDF is corrupt, empty, or password-protected.
    """
    if not pdf_bytes:
        raise PdfConversionError("PDF bytes are empty")

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PdfConversionError(f"Failed to open PDF: {exc}") from exc

    # Check for password protection
    if doc.is_encrypted:
        doc.close()
        raise PdfConversionError("PDF is password-protected")

    if doc.page_count == 0:
        doc.close()
        raise PdfConversionError("PDF has no pages")

    images: list[bytes] = []
    zoom = dpi / 72  # 72 is the default PDF DPI
    matrix = fitz.Matrix(zoom, zoom)

    try:
        pages_to_convert = min(doc.page_count, max_pages)
        for i in range(pages_to_convert):
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=matrix)
            # Convert to JPEG bytes
            img_bytes = pix.tobytes(output="jpeg", jpg_quality=90)
            images.append(img_bytes)
    except Exception as exc:
        raise PdfConversionError(f"Failed to render PDF page: {exc}") from exc
    finally:
        doc.close()

    return images


# ---------------------------------------------------------------------------
# extract_from_pdf()
# ---------------------------------------------------------------------------


async def extract_from_pdf(
    pdf_bytes: bytes,
    *,
    request_id: str,
):
    """Extract prescription data from a PDF document.

    Converts PDF to images, extracts each page, and merges results.
    For single-page PDFs, returns the result directly.
    For multi-page, merges medicines/lab_tests and uses highest-confidence shared fields.

    Raises:
        PdfConversionError: If PDF conversion fails.
        NotMedicalDocumentError: If all pages are doc_type='other'.
    """
    from backend.app.models.schemas import PrescriptionData
    from backend.app.services.extraction import (
        NotMedicalDocumentError,
        extract_prescription_from_bytes,
    )

    log = logger.bind(request_id=request_id)

    # Step 1: Convert PDF to images
    page_images = await convert_pdf_to_images(pdf_bytes)
    page_count = len(page_images)
    log.info("PDF conversion: pages={}", page_count)

    # Step 2: Extract each page
    results: list[PrescriptionData] = []
    for i, img_bytes in enumerate(page_images):
        start = time.monotonic()
        result = await extract_prescription_from_bytes(
            image_bytes=img_bytes,
            content_type="image/jpeg",
            request_id=f"{request_id}-page{i + 1}",
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)
        log.info("PDF page {}/{} extracted: latency_ms={}", i + 1, page_count, elapsed_ms)
        results.append(result)

    # Step 3: Single page — return directly
    if len(results) == 1:
        return results[0]

    # Step 4: Check if all pages are "other"
    if all(r.doc_type == "other" for r in results):
        raise NotMedicalDocumentError("No medical content found in any PDF page")

    # Step 5: Merge multi-page results
    # Find the page with the highest overall_confidence for shared fields
    best = max(results, key=lambda r: r.overall_confidence)

    # Merge medicines and lab_tests from all pages
    all_medicines = []
    all_lab_tests = []
    for r in results:
        all_medicines.extend(r.medicines)
        all_lab_tests.extend(r.lab_tests)

    return PrescriptionData(
        doctor_name=best.doctor_name,
        patient_name=best.patient_name,
        date=best.date,
        diagnosis=best.diagnosis,
        medicines=all_medicines,
        lab_tests=all_lab_tests,
        overall_confidence=best.overall_confidence,
        doc_type=best.doc_type,
    )
