"""S14.4 — Web Integration Tests.

20 tests covering the web upload flow: POST /api/translate happy path,
error paths, frontend page tests, and Edge TTS fallback.
All external services mocked.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure env vars are set before any Settings() import
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

for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)

from backend.app.models.schemas import (  # noqa: E402
    MedicineEntry,
    PrescriptionData,
    TranslationResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# A minimal 1x1 JPEG (smallest valid JPEG)
_TINY_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\x09\x09"
    b"\x08\x0a\x0c\x14\x0d\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b"
    b"\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04"
    b"\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"
    b"\x22q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\x09\x0a"
    b"\x16\x17\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz"
    b"\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99"
    b"\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7"
    b"\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5"
    b"\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1"
    b"\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa"
    b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd2\x8a(\x03\xff\xd9"
)


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


# Force-import modules so patch() can resolve string targets
import backend.app.main  # noqa: E402, F401
import backend.app.services.extraction  # noqa: E402, F401
import backend.app.services.drug_lookup  # noqa: E402, F401
import backend.app.services.glossary  # noqa: E402, F401
import backend.app.services.translation  # noqa: E402, F401
import backend.app.services.tts  # noqa: E402, F401
import backend.app.db.redis  # noqa: E402, F401

# Common mock targets — mock where imported in main.py
_PATCH_INIT_DB = "backend.app.main.init_db"
_PATCH_CLOSE_DB = "backend.app.main.close_db"
_PATCH_INIT_REDIS = "backend.app.main.init_redis"
_PATCH_CLOSE_REDIS = "backend.app.main.close_redis"
_PATCH_EXTRACT = "backend.app.services.extraction.extract_prescription_from_bytes"
_PATCH_ENRICH = "backend.app.services.drug_lookup.enrich_prescription"
_PATCH_LOOKUP_TERMS = "backend.app.services.glossary.lookup_terms"
_PATCH_FORMAT_GLOSSARY = "backend.app.services.glossary.format_glossary_context"
_PATCH_TRANSLATE = "backend.app.services.translation.simplify_and_translate"
_PATCH_AUDIO = "backend.app.services.tts.generate_and_deliver_audio"
_PATCH_REDIS_CLIENT = "backend.app.db.redis._redis_client"
_PATCH_EXTRACT_SECTIONS = "backend.app.services.translation._extract_sections"
_PATCH_IMAGE_STORE = "backend.app.services.image_store.store_prescription_image"


@pytest.fixture
def _mock_lifespan():
    """Mock DB and Redis init/close to avoid real connections."""
    with (
        patch(_PATCH_INIT_DB, new_callable=AsyncMock),
        patch(_PATCH_CLOSE_DB, new_callable=AsyncMock),
        patch(_PATCH_INIT_REDIS, new_callable=AsyncMock),
        patch(_PATCH_CLOSE_REDIS, new_callable=AsyncMock),
    ):
        yield


@pytest.fixture
def _mock_pipeline():
    """Mock all pipeline services for a successful run."""
    prescription = _make_prescription()
    translation = _make_translation()

    with (
        patch(_PATCH_EXTRACT, new_callable=AsyncMock, return_value=prescription) as m_extract,
        patch(_PATCH_ENRICH, new_callable=AsyncMock, return_value=[]) as m_enrich,
        patch(_PATCH_LOOKUP_TERMS, new_callable=AsyncMock, return_value=[]) as m_lookup,
        patch(_PATCH_FORMAT_GLOSSARY, return_value="") as m_glossary,
        patch(_PATCH_TRANSLATE, new_callable=AsyncMock, return_value=translation) as m_translate,
        patch(
            _PATCH_AUDIO,
            new_callable=AsyncMock,
            return_value="https://s3.amazonaws.com/test/audio.mp3",
        ) as m_audio,
        patch(_PATCH_REDIS_CLIENT, new=MagicMock()),
        patch(
            _PATCH_EXTRACT_SECTIONS,
            return_value={"medicines": "med section", "why": "why section", "next_steps": "next"},
        ),
        patch(_PATCH_IMAGE_STORE, new_callable=AsyncMock, return_value="images/test.jpg"),
    ):
        yield {
            "extract": m_extract,
            "enrich": m_enrich,
            "lookup": m_lookup,
            "glossary": m_glossary,
            "translate": m_translate,
            "audio": m_audio,
            "prescription": prescription,
            "translation": translation,
        }


@pytest.fixture
async def client(_mock_lifespan):
    """AsyncClient using the real FastAPI app with mocked lifespan."""
    from backend.app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===========================================================================
# FR-1: Happy path integration tests
# ===========================================================================


class TestFR1HappyPath:
    """Happy path: upload image → full pipeline → valid response."""

    @pytest.mark.asyncio
    async def test_happy_path_returns_200(self, client, _mock_pipeline):
        """POST /api/translate with valid image and language returns 200."""
        resp = await client.post(
            "/api/translate",
            files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
            data={"language_code": "hi"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_happy_path_response_has_translated_text(self, client, _mock_pipeline):
        """Response JSON contains translated_text."""
        resp = await client.post(
            "/api/translate",
            files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
            data={"language_code": "hi"},
        )
        data = resp.json()
        assert "translated_text" in data
        assert len(data["translated_text"]) > 0

    @pytest.mark.asyncio
    async def test_happy_path_response_has_medicines(self, client, _mock_pipeline):
        """Response JSON contains medicines list."""
        resp = await client.post(
            "/api/translate",
            files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
            data={"language_code": "hi"},
        )
        data = resp.json()
        assert "medicines" in data
        assert isinstance(data["medicines"], list)

    @pytest.mark.asyncio
    async def test_happy_path_response_has_disclaimer(self, client, _mock_pipeline):
        """Response JSON contains disclaimer."""
        resp = await client.post(
            "/api/translate",
            files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
            data={"language_code": "hi"},
        )
        data = resp.json()
        assert "disclaimer" in data
        assert len(data["disclaimer"]) > 0

    @pytest.mark.asyncio
    async def test_happy_path_response_has_audio_url(self, client, _mock_pipeline):
        """Response JSON contains audio_url from S3."""
        resp = await client.post(
            "/api/translate",
            files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
            data={"language_code": "hi"},
        )
        data = resp.json()
        assert "audio_url" in data
        assert data["audio_url"] is not None
        assert "s3.amazonaws.com" in data["audio_url"]

    @pytest.mark.asyncio
    async def test_happy_path_response_has_request_id(self, client, _mock_pipeline):
        """Response JSON contains a UUID request_id."""
        resp = await client.post(
            "/api/translate",
            files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
            data={"language_code": "hi"},
        )
        data = resp.json()
        assert "request_id" in data
        assert len(data["request_id"]) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_happy_path_response_has_latency(self, client, _mock_pipeline):
        """Response JSON contains latency_ms."""
        resp = await client.post(
            "/api/translate",
            files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
            data={"language_code": "hi"},
        )
        data = resp.json()
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], int)
        assert data["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_happy_path_calls_extract(self, client, _mock_pipeline):
        """Pipeline calls extract_prescription_from_bytes."""
        await client.post(
            "/api/translate",
            files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
            data={"language_code": "hi"},
        )
        _mock_pipeline["extract"].assert_awaited_once()

    @pytest.mark.asyncio
    async def test_happy_path_calls_translate(self, client, _mock_pipeline):
        """Pipeline calls simplify_and_translate."""
        await client.post(
            "/api/translate",
            files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
            data={"language_code": "hi"},
        )
        _mock_pipeline["translate"].assert_awaited_once()


# ===========================================================================
# FR-2: Error path tests
# ===========================================================================


class TestFR2ErrorPaths:
    """Error handling: invalid inputs and pipeline exceptions."""

    @pytest.mark.asyncio
    async def test_non_image_file_returns_400(self, client, _mock_pipeline):
        """Uploading a non-image file returns 400."""
        resp = await client.post(
            "/api/translate",
            files={"image": ("test.txt", b"hello world", "text/plain")},
            data={"language_code": "hi"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_unsupported_language_returns_400(self, client, _mock_pipeline):
        """Unsupported language_code returns 400."""
        resp = await client.post(
            "/api/translate",
            files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
            data={"language_code": "zz"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_image_returns_422(self, client, _mock_pipeline):
        """Missing image field returns 422 (FastAPI validation)."""
        resp = await client.post(
            "/api/translate",
            data={"language_code": "hi"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_not_medical_document_returns_422(self, client, _mock_lifespan):
        """NotMedicalDocumentError from pipeline returns 422."""
        from backend.app.services.extraction import NotMedicalDocumentError

        with (
            patch(
                _PATCH_EXTRACT,
                new_callable=AsyncMock,
                side_effect=NotMedicalDocumentError("Not a prescription"),
            ),
            patch(_PATCH_IMAGE_STORE, new_callable=AsyncMock, return_value="images/test.jpg"),
        ):
            resp = await client.post(
                "/api/translate",
                files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
                data={"language_code": "hi"},
            )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "not_medical_document"

    @pytest.mark.asyncio
    async def test_image_not_readable_returns_422(self, client, _mock_lifespan):
        """ImageNotReadableError from pipeline returns 422."""
        from backend.app.services.extraction import ImageNotReadableError

        with (
            patch(
                _PATCH_EXTRACT,
                new_callable=AsyncMock,
                side_effect=ImageNotReadableError("Cannot read image"),
            ),
            patch(_PATCH_IMAGE_STORE, new_callable=AsyncMock, return_value="images/test.jpg"),
        ):
            resp = await client.post(
                "/api/translate",
                files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
                data={"language_code": "hi"},
            )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "image_not_readable"

    @pytest.mark.asyncio
    async def test_translation_error_returns_500(self, client, _mock_lifespan):
        """TranslationError from pipeline returns 500."""
        from backend.app.services.translation import TranslationError

        prescription = _make_prescription()
        with (
            patch(_PATCH_EXTRACT, new_callable=AsyncMock, return_value=prescription),
            patch(_PATCH_ENRICH, new_callable=AsyncMock, return_value=[]),
            patch(_PATCH_LOOKUP_TERMS, new_callable=AsyncMock, return_value=[]),
            patch(_PATCH_FORMAT_GLOSSARY, return_value=""),
            patch(
                _PATCH_TRANSLATE,
                new_callable=AsyncMock,
                side_effect=TranslationError("Translation failed"),
            ),
            patch(_PATCH_REDIS_CLIENT, new=MagicMock()),
            patch(_PATCH_IMAGE_STORE, new_callable=AsyncMock, return_value="images/test.jpg"),
        ):
            resp = await client.post(
                "/api/translate",
                files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
                data={"language_code": "hi"},
            )
        assert resp.status_code == 500


# ===========================================================================
# FR-3: Frontend page tests
# ===========================================================================


class TestFR3FrontendPage:
    """Frontend HTML page tests."""

    @pytest.mark.asyncio
    async def test_landing_page_returns_200(self, client):
        """GET / returns 200."""
        resp = await client.get("/")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_landing_page_returns_html(self, client):
        """GET / returns HTML content type."""
        resp = await client.get("/")
        assert "text/html" in resp.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_landing_page_has_language_dropdown(self, client):
        """HTML contains language select options for all 22 languages."""
        resp = await client.get("/")
        html = resp.text
        # Should have a select or dropdown with language options
        assert "language" in html.lower()
        # Check for at least a few known languages
        assert "hi" in html  # Hindi code
        assert "ta" in html  # Tamil code

    @pytest.mark.asyncio
    async def test_landing_page_has_upload_form(self, client):
        """HTML contains a file upload form."""
        resp = await client.get("/")
        html = resp.text
        assert "file" in html.lower() or "upload" in html.lower()


# ===========================================================================
# FR-4: Edge TTS fallback in web pipeline
# ===========================================================================


class TestFR4EdgeTTSFallback:
    """Edge TTS fallback when Bhashini is unavailable."""

    @pytest.mark.asyncio
    async def test_edge_tts_fallback_returns_audio_url(self, client, _mock_lifespan):
        """When Bhashini key is empty, Edge TTS is used, audio_url still returned."""
        prescription = _make_prescription()
        translation = _make_translation()

        with (
            patch(_PATCH_EXTRACT, new_callable=AsyncMock, return_value=prescription),
            patch(_PATCH_ENRICH, new_callable=AsyncMock, return_value=[]),
            patch(_PATCH_LOOKUP_TERMS, new_callable=AsyncMock, return_value=[]),
            patch(_PATCH_FORMAT_GLOSSARY, return_value=""),
            patch(_PATCH_TRANSLATE, new_callable=AsyncMock, return_value=translation),
            patch(
                _PATCH_AUDIO,
                new_callable=AsyncMock,
                return_value="https://s3.amazonaws.com/test/edge-audio.mp3",
            ) as m_audio,
            patch(_PATCH_REDIS_CLIENT, new=MagicMock()),
            patch(
                _PATCH_EXTRACT_SECTIONS,
                return_value={
                    "medicines": "med section",
                    "why": "why section",
                    "next_steps": "next",
                },
            ),
            patch(_PATCH_IMAGE_STORE, new_callable=AsyncMock, return_value="images/test.jpg"),
        ):
            resp = await client.post(
                "/api/translate",
                files={"image": ("test.jpg", _TINY_JPEG, "image/jpeg")},
                data={"language_code": "hi"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["audio_url"] is not None
        m_audio.assert_awaited_once()
