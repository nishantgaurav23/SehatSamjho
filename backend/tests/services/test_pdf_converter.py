"""S14.5 — PDF Upload Support — Unit Tests for pdf_converter.py.

18 tests covering:
- Module import, function signatures
- is_pdf() detection
- convert_pdf_to_images() single/multi page, max_pages, errors
- extract_from_pdf() single page, multi-page merge, all-other, confidence, logging
- PdfConversionError exception class
"""

from __future__ import annotations

import inspect
import os
from unittest.mock import AsyncMock, patch

import fitz  # PyMuPDF
import pytest

# Ensure env vars before any Settings() import
_TEST_ENV = {
    "OPENAI_API_KEY": "sk-test-openai",
    "ANTHROPIC_API_KEY": "sk-ant-test-anthropic",
    "TWILIO_ACCOUNT_SID": "ACtest1234567890",
    "TWILIO_AUTH_TOKEN": "test-twilio-token",
    "TWILIO_WHATSAPP_FROM": "whatsapp:+14155238886",
    "BHASHINI_API_KEY": "test-bhashini-key",
    "BHASHINI_USER_ID": "test-bhashini-user",
    "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "S3_BUCKET": "test-bucket",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/testdb",
    "REDIS_URL": "redis://localhost:6379/0",
}
for _k, _v in _TEST_ENV.items():
    os.environ.setdefault(_k, _v)


# ---------------------------------------------------------------------------
# Helpers: create real PDFs in memory using PyMuPDF
# ---------------------------------------------------------------------------


def _make_pdf(num_pages: int = 1) -> bytes:
    """Create a minimal valid PDF with the given number of pages."""
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=200, height=200)
        page.insert_text((50, 100), f"Page {i + 1}", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _make_password_protected_pdf() -> bytes:
    """Create a password-protected PDF."""
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_text((50, 100), "Secret", fontsize=12)
    pdf_bytes = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret123")
    doc.close()
    return pdf_bytes


# ---------------------------------------------------------------------------
# Helpers: mock PrescriptionData
# ---------------------------------------------------------------------------

from backend.app.models.schemas import MedicineEntry, PrescriptionData  # noqa: E402


def _make_prescription(**overrides) -> PrescriptionData:
    defaults = {
        "doctor_name": "Dr. Sharma",
        "medicines": [
            MedicineEntry(
                medicine_name="Paracetamol 500mg",
                dosage="500mg",
                frequency="Twice daily",
                duration="5 days",
                confidence=0.95,
            ),
        ],
        "lab_tests": [],
        "overall_confidence": 0.9,
        "doc_type": "prescription",
        "diagnosis": "Fever",
        "date": "2024-01-15",
    }
    defaults.update(overrides)
    return PrescriptionData(**defaults)


# ===========================================================================
# Test 1: Module importable
# ===========================================================================


class TestImport:
    def test_import(self):
        """pdf_converter module is importable."""
        import backend.app.services.pdf_converter  # noqa: F401


# ===========================================================================
# Test 2: convert_pdf_to_images signature
# ===========================================================================


class TestConvertSignature:
    def test_convert_pdf_to_images_signature(self):
        """convert_pdf_to_images accepts (pdf_bytes, *, max_pages, dpi)."""
        from backend.app.services.pdf_converter import convert_pdf_to_images

        sig = inspect.signature(convert_pdf_to_images)
        params = list(sig.parameters.keys())
        assert "pdf_bytes" in params
        assert "max_pages" in params
        assert "dpi" in params
        # max_pages and dpi are keyword-only
        assert sig.parameters["max_pages"].kind == inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters["dpi"].kind == inspect.Parameter.KEYWORD_ONLY


# ===========================================================================
# Tests 3-5: is_pdf()
# ===========================================================================


class TestIsPdf:
    def test_is_pdf_with_pdf_content_type(self):
        """is_pdf returns True for application/pdf content type."""
        from backend.app.services.pdf_converter import is_pdf

        assert is_pdf("application/pdf", b"") is True

    def test_is_pdf_with_magic_bytes(self):
        """is_pdf returns True when bytes start with %PDF magic."""
        from backend.app.services.pdf_converter import is_pdf

        assert is_pdf("", b"%PDF-1.4 some content") is True

    def test_is_pdf_with_image(self):
        """is_pdf returns False for image content."""
        from backend.app.services.pdf_converter import is_pdf

        assert is_pdf("image/jpeg", b"\xff\xd8\xff\xe0") is False


# ===========================================================================
# Tests 6-12: convert_pdf_to_images()
# ===========================================================================


class TestConvertPdfToImages:
    @pytest.mark.asyncio
    async def test_convert_single_page_pdf(self):
        """1-page PDF returns list with 1 JPEG bytes."""
        from backend.app.services.pdf_converter import convert_pdf_to_images

        pdf = _make_pdf(1)
        result = await convert_pdf_to_images(pdf)
        assert len(result) == 1
        assert isinstance(result[0], bytes)

    @pytest.mark.asyncio
    async def test_convert_multi_page_pdf(self):
        """3-page PDF returns list with 3 JPEG bytes."""
        from backend.app.services.pdf_converter import convert_pdf_to_images

        pdf = _make_pdf(3)
        result = await convert_pdf_to_images(pdf)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_convert_respects_max_pages(self):
        """10-page PDF with max_pages=2 returns 2 items."""
        from backend.app.services.pdf_converter import convert_pdf_to_images

        pdf = _make_pdf(10)
        result = await convert_pdf_to_images(pdf, max_pages=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_convert_corrupt_pdf_raises(self):
        """Corrupt bytes raise PdfConversionError."""
        from backend.app.services.pdf_converter import PdfConversionError, convert_pdf_to_images

        with pytest.raises(PdfConversionError):
            await convert_pdf_to_images(b"not a pdf at all")

    @pytest.mark.asyncio
    async def test_convert_empty_pdf_raises(self):
        """Empty bytes raise PdfConversionError."""
        from backend.app.services.pdf_converter import PdfConversionError, convert_pdf_to_images

        with pytest.raises(PdfConversionError):
            await convert_pdf_to_images(b"")

    @pytest.mark.asyncio
    async def test_convert_password_protected_raises(self):
        """Password-protected PDF raises PdfConversionError."""
        from backend.app.services.pdf_converter import PdfConversionError, convert_pdf_to_images

        pdf = _make_password_protected_pdf()
        with pytest.raises(PdfConversionError):
            await convert_pdf_to_images(pdf)

    @pytest.mark.asyncio
    async def test_output_is_valid_jpeg(self):
        """Output bytes start with JPEG magic bytes."""
        from backend.app.services.pdf_converter import convert_pdf_to_images

        pdf = _make_pdf(1)
        result = await convert_pdf_to_images(pdf)
        assert result[0][:3] == b"\xff\xd8\xff"


# ===========================================================================
# Tests 13-17: extract_from_pdf()
# ===========================================================================

_PATCH_EXTRACT_FROM_BYTES = "backend.app.services.extraction.extract_prescription_from_bytes"
_PATCH_CONVERT = "backend.app.services.pdf_converter.convert_pdf_to_images"


class TestExtractFromPdf:
    @pytest.mark.asyncio
    async def test_extract_from_pdf_single_page(self):
        """Single page: calls extract_prescription_from_bytes once, returns its result."""
        from backend.app.services.pdf_converter import extract_from_pdf

        prescription = _make_prescription()
        with (
            patch(
                _PATCH_CONVERT,
                new_callable=AsyncMock,
                return_value=[b"\xff\xd8\xff\xe0page1"],
            ),
            patch(
                _PATCH_EXTRACT_FROM_BYTES,
                new_callable=AsyncMock,
                return_value=prescription,
            ) as m_extract,
        ):
            result = await extract_from_pdf(b"fake-pdf", request_id="req-1")
        assert result == prescription
        m_extract.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_extract_from_pdf_multi_page_merges(self):
        """2 pages with different medicines are merged."""
        from backend.app.services.pdf_converter import extract_from_pdf

        p1 = _make_prescription(
            medicines=[
                MedicineEntry(medicine_name="Drug A", confidence=0.9),
            ],
            overall_confidence=0.8,
        )
        p2 = _make_prescription(
            medicines=[
                MedicineEntry(medicine_name="Drug B", confidence=0.85),
            ],
            overall_confidence=0.95,
        )

        with (
            patch(
                _PATCH_CONVERT,
                new_callable=AsyncMock,
                return_value=[b"img1", b"img2"],
            ),
            patch(
                _PATCH_EXTRACT_FROM_BYTES,
                new_callable=AsyncMock,
                side_effect=[p1, p2],
            ),
        ):
            result = await extract_from_pdf(b"fake-pdf", request_id="req-2")

        # Medicines are merged
        med_names = [m.medicine_name for m in result.medicines]
        assert "Drug A" in med_names
        assert "Drug B" in med_names

    @pytest.mark.asyncio
    async def test_extract_from_pdf_all_other_raises(self):
        """All pages doc_type='other' raises NotMedicalDocumentError."""
        from backend.app.services.extraction import NotMedicalDocumentError
        from backend.app.services.pdf_converter import extract_from_pdf

        p1 = _make_prescription(doc_type="other", overall_confidence=0.3)
        p2 = _make_prescription(doc_type="other", overall_confidence=0.2)

        with (
            patch(
                _PATCH_CONVERT,
                new_callable=AsyncMock,
                return_value=[b"img1", b"img2"],
            ),
            patch(
                _PATCH_EXTRACT_FROM_BYTES,
                new_callable=AsyncMock,
                side_effect=[p1, p2],
            ),
        ):
            with pytest.raises(NotMedicalDocumentError):
                await extract_from_pdf(b"fake-pdf", request_id="req-3")

    @pytest.mark.asyncio
    async def test_extract_from_pdf_highest_confidence(self):
        """Picks highest confidence for shared fields like doctor_name."""
        from backend.app.services.pdf_converter import extract_from_pdf

        p1 = _make_prescription(
            doctor_name="Dr. Low",
            diagnosis="Cold",
            overall_confidence=0.7,
            medicines=[MedicineEntry(medicine_name="Drug A", confidence=0.9)],
        )
        p2 = _make_prescription(
            doctor_name="Dr. High",
            diagnosis="Flu",
            overall_confidence=0.95,
            medicines=[MedicineEntry(medicine_name="Drug B", confidence=0.85)],
        )

        with (
            patch(
                _PATCH_CONVERT,
                new_callable=AsyncMock,
                return_value=[b"img1", b"img2"],
            ),
            patch(
                _PATCH_EXTRACT_FROM_BYTES,
                new_callable=AsyncMock,
                side_effect=[p1, p2],
            ),
        ):
            result = await extract_from_pdf(b"fake-pdf", request_id="req-4")

        # Highest confidence page's shared fields win
        assert result.doctor_name == "Dr. High"
        assert result.diagnosis == "Flu"

    @pytest.mark.asyncio
    async def test_extract_from_pdf_logs_page_count(self, capfd):
        """Loguru output includes page count."""
        from backend.app.services.pdf_converter import extract_from_pdf

        prescription = _make_prescription()
        with (
            patch(
                _PATCH_CONVERT,
                new_callable=AsyncMock,
                return_value=[b"img1", b"img2"],
            ),
            patch(
                _PATCH_EXTRACT_FROM_BYTES,
                new_callable=AsyncMock,
                return_value=prescription,
            ),
            patch("backend.app.services.pdf_converter.logger") as mock_logger,
        ):
            mock_logger.bind.return_value = mock_logger
            await extract_from_pdf(b"fake-pdf", request_id="req-5")

        # Check that logger.info was called with page count info
        log_calls = [str(c) for c in mock_logger.info.call_args_list]
        page_logged = any("2" in c and "page" in c.lower() for c in log_calls)
        assert page_logged, f"Expected page count in logs, got: {log_calls}"


# ===========================================================================
# Test 18: PdfConversionError class
# ===========================================================================


class TestPdfConversionError:
    def test_pdf_conversion_error_class(self):
        """PdfConversionError is a subclass of Exception."""
        from backend.app.services.pdf_converter import PdfConversionError

        assert issubclass(PdfConversionError, Exception)
        err = PdfConversionError("test error")
        assert str(err) == "test error"
