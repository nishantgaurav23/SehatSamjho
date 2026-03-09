"""S14.5 — PDF Upload Support — API Tests for web PDF endpoint.

2 tests:
- test_web_translate_accepts_pdf: POST with PDF → 200
- test_web_translate_rejects_unsupported: POST with .docx → 400
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import fitz
import pytest
from httpx import ASGITransport, AsyncClient

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

from backend.app.models.schemas import (  # noqa: E402
    MedicineEntry,
    PrescriptionData,
    TranslationResult,
)

import backend.app.main  # noqa: E402, F401
import backend.app.services.extraction  # noqa: E402, F401
import backend.app.services.drug_lookup  # noqa: E402, F401
import backend.app.services.glossary  # noqa: E402, F401
import backend.app.services.translation  # noqa: E402, F401
import backend.app.services.tts  # noqa: E402, F401
import backend.app.db.redis  # noqa: E402, F401

# Mock targets
_PATCH_INIT_DB = "backend.app.main.init_db"
_PATCH_CLOSE_DB = "backend.app.main.close_db"
_PATCH_INIT_REDIS = "backend.app.main.init_redis"
_PATCH_CLOSE_REDIS = "backend.app.main.close_redis"
_PATCH_EXTRACT_FROM_PDF = "backend.app.services.pdf_converter.extract_from_pdf"
_PATCH_EXTRACT = "backend.app.services.extraction.extract_prescription_from_bytes"
_PATCH_ENRICH = "backend.app.services.drug_lookup.enrich_prescription"
_PATCH_LOOKUP_TERMS = "backend.app.services.glossary.lookup_terms"
_PATCH_FORMAT_GLOSSARY = "backend.app.services.glossary.format_glossary_context"
_PATCH_TRANSLATE = "backend.app.services.translation.simplify_and_translate"
_PATCH_AUDIO = "backend.app.services.tts.generate_and_deliver_audio"
_PATCH_REDIS_CLIENT = "backend.app.db.redis._redis_client"
_PATCH_EXTRACT_SECTIONS = "backend.app.services.translation._extract_sections"
_PATCH_IMAGE_STORE = "backend.app.services.image_store.store_prescription_image"


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


def _make_translation(**overrides) -> TranslationResult:
    defaults = {
        "translated_text": (
            "## 💊 Medicines\nParacetamol for fever.\n\n"
            "## 🔍 Why\nFor fever relief.\n\n"
            "## ✅ Next Steps\nTake rest."
        ),
        "per_medicine_summaries": ["Paracetamol: for fever, take 500mg twice daily"],
        "disclaimer": "This is an AI translation. Consult your doctor.",
        "language_code": "hi",
        "translated_diagnosis": "बुखार",
    }
    defaults.update(overrides)
    return TranslationResult(**defaults)


def _make_pdf(num_pages: int = 1) -> bytes:
    """Create a minimal valid PDF."""
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=200, height=200)
        page.insert_text((50, 100), f"Page {i + 1}", fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def _mock_lifespan():
    with (
        patch(_PATCH_INIT_DB, new_callable=AsyncMock),
        patch(_PATCH_CLOSE_DB, new_callable=AsyncMock),
        patch(_PATCH_INIT_REDIS, new_callable=AsyncMock),
        patch(_PATCH_CLOSE_REDIS, new_callable=AsyncMock),
    ):
        yield


@pytest.fixture
async def client(_mock_lifespan):
    from backend.app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestWebPdf:
    @pytest.mark.asyncio
    async def test_web_translate_accepts_pdf(self, client):
        """POST /api/translate with PDF → 200, response has page_count."""
        prescription = _make_prescription()
        translation = _make_translation()
        pdf_bytes = _make_pdf(2)

        with (
            patch(
                _PATCH_EXTRACT_FROM_PDF,
                new_callable=AsyncMock,
                return_value=prescription,
            ),
            patch(_PATCH_ENRICH, new_callable=AsyncMock, return_value=[]),
            patch(_PATCH_LOOKUP_TERMS, new_callable=AsyncMock, return_value=[]),
            patch(_PATCH_FORMAT_GLOSSARY, return_value=""),
            patch(_PATCH_TRANSLATE, new_callable=AsyncMock, return_value=translation),
            patch(
                _PATCH_AUDIO,
                new_callable=AsyncMock,
                return_value="https://s3.amazonaws.com/test/audio.mp3",
            ),
            patch(_PATCH_REDIS_CLIENT, new=MagicMock()),
            patch(
                _PATCH_EXTRACT_SECTIONS,
                return_value={
                    "medicines": "med section",
                    "why": "why section",
                    "next_steps": "next",
                },
            ),
            patch(_PATCH_IMAGE_STORE, new_callable=AsyncMock, return_value="docs/test.pdf"),
        ):
            resp = await client.post(
                "/api/translate",
                files={"file": ("prescription.pdf", pdf_bytes, "application/pdf")},
                data={"language_code": "hi"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "page_count" in data
        assert "translated_text" in data

    @pytest.mark.asyncio
    async def test_web_translate_rejects_unsupported(self, client):
        """POST /api/translate with .docx returns 400."""
        resp = await client.post(
            "/api/translate",
            files={
                "file": (
                    "document.docx",
                    b"PK\x03\x04fake-docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"language_code": "hi"},
        )
        assert resp.status_code == 400
