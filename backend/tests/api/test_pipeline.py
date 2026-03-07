"""S10.5 — Pipeline Integration Tests.

20 tests covering the full end-to-end pipeline through the HTTP webhook endpoint.
POST /webhook/whatsapp with a valid image payload → full pipeline execution →
correct Twilio calls, interaction logging, session cleanup.
All external services mocked. Uses httpx.AsyncClient + ASGITransport for HTTP-level tests.
"""

from __future__ import annotations

import json
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

# ---------------------------------------------------------------------------
# Ensure test env vars are set BEFORE importing modules that read settings
# ---------------------------------------------------------------------------
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
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
}
for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from backend.app.api.webhooks import (  # noqa: E402
    GENERIC_PIPELINE_ERROR_MESSAGE,
    IMAGE_NOT_READABLE_MESSAGE,
    NOT_MEDICAL_DOC_MESSAGE,
    PROCESSING_ACK_MESSAGE,
    TRANSLATION_ERROR_MESSAGE,
)
from backend.app.core.security import validate_twilio_signature  # noqa: E402
from backend.app.db.redis import get_redis  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.models.schemas import (  # noqa: E402
    MedicineEntry,
    PrescriptionData,
    SessionStatus,
    TranslationResult,
    DrugInfo,
    GlossaryEntry,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PHONE = "whatsapp:+919876543210"
MEDIA_URL = "https://api.twilio.com/media/test-image.jpg"
AUDIO_URL = "https://s3.amazonaws.com/audio/test.ogg"


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------


def _make_prescription(**overrides) -> PrescriptionData:
    defaults = {
        "doctor_name": "Dr. Sharma",
        "medicines": [
            MedicineEntry(
                medicine_name="Paracetamol",
                dosage="500mg",
                frequency="3 times a day",
                duration="5 days",
                confidence=0.95,
            ),
            MedicineEntry(
                medicine_name="Amoxicillin",
                dosage="250mg",
                frequency="2 times a day",
                duration="7 days",
                confidence=0.85,
            ),
        ],
        "overall_confidence": 0.9,
    }
    defaults.update(overrides)
    return PrescriptionData(**defaults)


def _make_translation_result(**overrides) -> TranslationResult:
    defaults = {
        "translated_text": "Your prescription contains Paracetamol 500mg and Amoxicillin 250mg.",
        "per_medicine_summaries": [
            "Paracetamol: pain and fever relief",
            "Amoxicillin: antibiotic for infections",
        ],
        "disclaimer": "This is not medical advice. Consult your doctor.",
        "language_code": "hi",
    }
    defaults.update(overrides)
    return TranslationResult(**defaults)


def _make_drug_info_list() -> list[DrugInfo | None]:
    return [
        DrugInfo(brand_name="Crocin", generic_name="Paracetamol", purpose_en="Pain relief"),
        None,
    ]


def _make_glossary_entries() -> list[GlossaryEntry]:
    return [
        GlossaryEntry(
            term="Paracetamol",
            explanation="pain and fever reducer",
            vernacular="दर्द और बुखार कम करने वाली दवा",
        ),
    ]


def _make_session_json(**overrides) -> str:
    """Create session JSON that Redis would return."""
    defaults = {
        "status": SessionStatus.WAITING_FOR_IMAGE.value,
        "language_code": "hi",
        "language_name": "Hindi",
        "request_id": "original-req-id",
        "created_at": "2026-01-01T00:00:00Z",
    }
    defaults.update(overrides)
    return json.dumps(defaults)


def _form_data(**overrides) -> dict:
    """Build valid Twilio form data for an image webhook."""
    data = {
        "From": PHONE,
        "Body": "",
        "NumMedia": "1",
        "MediaUrl0": MEDIA_URL,
        "MediaContentType0": "image/jpeg",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_services():
    """Patch all external services and return their mocks for assertions."""
    prescription = _make_prescription()
    drug_info_list = _make_drug_info_list()
    glossary_entries = _make_glossary_entries()
    translation_result = _make_translation_result()

    patches = {
        "download_image": patch(
            "backend.app.api.webhooks._download_image",
            new_callable=AsyncMock,
            return_value=b"fake-image-bytes",
        ),
        "store_image": patch(
            "backend.app.api.webhooks.store_prescription_image",
            new_callable=AsyncMock,
            return_value="prescriptions/test/img.jpg",
        ),
        "extract": patch(
            "backend.app.api.webhooks.extract_prescription_from_bytes",
            new_callable=AsyncMock,
            return_value=prescription,
        ),
        "enrich": patch(
            "backend.app.api.webhooks.enrich_prescription",
            new_callable=AsyncMock,
            return_value=drug_info_list,
        ),
        "lookup": patch(
            "backend.app.api.webhooks.lookup_terms",
            new_callable=AsyncMock,
            return_value=glossary_entries,
        ),
        "format_glossary": patch(
            "backend.app.api.webhooks.format_glossary_context",
            return_value="Glossary:\nParacetamol → pain and fever reducer",
        ),
        "translate": patch(
            "backend.app.api.webhooks.simplify_and_translate",
            new_callable=AsyncMock,
            return_value=translation_result,
        ),
        "audio": patch(
            "backend.app.api.webhooks.generate_and_deliver_audio",
            new_callable=AsyncMock,
            return_value=AUDIO_URL,
        ),
        "send_text": patch(
            "backend.app.api.webhooks.send_text_message",
            new_callable=AsyncMock,
        ),
        "send_audio_fallback": patch(
            "backend.app.api.webhooks.send_audio_message_with_fallback",
            new_callable=AsyncMock,
            return_value=("sid123", True),
        ),
        "log_interaction": patch(
            "backend.app.api.webhooks._log_interaction",
            new_callable=AsyncMock,
        ),
    }

    mocks = {}
    entered = []
    for name, p in patches.items():
        m = p.start()
        entered.append(p)
        mocks[name] = m

    # Mock AsyncSessionLocal as async context manager
    mock_db_session = AsyncMock()

    @asynccontextmanager
    async def mock_session_factory():
        yield mock_db_session

    session_local_patch = patch(
        "backend.app.api.webhooks.AsyncSessionLocal",
        side_effect=mock_session_factory,
    )
    mocks["session_local"] = session_local_patch.start()
    entered.append(session_local_patch)
    mocks["db_session"] = mock_db_session

    # Attach data objects for assertions
    mocks["prescription"] = prescription
    mocks["drug_info_list"] = drug_info_list
    mocks["glossary_entries"] = glossary_entries
    mocks["translation_result"] = translation_result

    yield mocks

    for p in entered:
        p.stop()


@pytest.fixture
def app(mock_services):
    """Create test app with HMAC bypass and mock Redis returning a WAITING_FOR_IMAGE session."""
    app = create_app()
    # Bypass HMAC validation
    app.dependency_overrides[validate_twilio_signature] = lambda: None

    # Mock Redis to return a WAITING_FOR_IMAGE session
    session_json = _make_session_json()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=session_json)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()

    async def _mock_redis_dep():
        yield mock_redis

    app.dependency_overrides[get_redis] = _mock_redis_dep
    mock_services["redis"] = mock_redis

    yield app
    app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    """Async HTTP client for the test app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ===========================================================================
# T1: File exists
# ===========================================================================


def test_pipeline_test_file_exists():
    """T1: test_pipeline.py exists in backend/tests/api/."""
    path = Path(__file__)
    assert path.name == "test_pipeline.py"
    assert path.parent.name == "api"
    assert path.exists()


# ===========================================================================
# T2–T7: Happy path
# ===========================================================================


class TestHappyPath:
    """HTTP-level happy path: image webhook → full pipeline → correct responses."""

    @pytest.mark.asyncio
    async def test_happy_path_http_200(self, client, mock_services):
        """T2: POST webhook with image → HTTP 200 TwiML response."""
        resp = await client.post("/webhook/whatsapp", data=_form_data())
        assert resp.status_code == 200
        assert "<Response/>" in resp.text

    @pytest.mark.asyncio
    async def test_happy_path_sends_text_reply(self, client, mock_services):
        """T3: Text reply sent with medicine names and disclaimer."""
        await client.post("/webhook/whatsapp", data=_form_data())

        # Find the reply text send call (not the ack)
        send_calls = mock_services["send_text"].call_args_list
        reply_calls = [c for c in send_calls if c.args[1] != PROCESSING_ACK_MESSAGE]
        assert len(reply_calls) >= 1
        reply_text = reply_calls[0].args[1]
        assert "Paracetamol" in reply_text
        assert mock_services["translation_result"].disclaimer in reply_text

    @pytest.mark.asyncio
    async def test_happy_path_sends_audio(self, client, mock_services):
        """T4: Audio message sent with presigned URL and fallback text."""
        await client.post("/webhook/whatsapp", data=_form_data())

        mock_services["send_audio_fallback"].assert_awaited_once()
        call_args = mock_services["send_audio_fallback"].call_args
        assert call_args.args[0] == PHONE
        assert call_args.args[1] == AUDIO_URL
        assert "fallback_text" in call_args.kwargs
        assert len(call_args.kwargs["fallback_text"]) > 0

    @pytest.mark.asyncio
    async def test_happy_path_logs_interaction_success(self, client, mock_services):
        """T5: Interaction logged with status=SUCCESS, latency_ms, confidence_avg."""
        from backend.app.db.models import InteractionStatus

        await client.post("/webhook/whatsapp", data=_form_data())

        mock_services["log_interaction"].assert_awaited_once()
        kwargs = mock_services["log_interaction"].call_args.kwargs
        assert kwargs["status"] == InteractionStatus.SUCCESS
        assert isinstance(kwargs["latency_ms"], int)
        assert kwargs["latency_ms"] >= 0
        # confidence_avg = (0.95 + 0.85) / 2 = 0.9
        assert kwargs["confidence_avg"] is not None
        assert abs(kwargs["confidence_avg"] - 0.9) < 0.01

    @pytest.mark.asyncio
    async def test_happy_path_session_deleted(self, client, mock_services):
        """T6: Session deleted from Redis after success."""
        await client.post("/webhook/whatsapp", data=_form_data())

        mock_redis = mock_services["redis"]
        mock_redis.delete.assert_called()
        # Verify it was called with the session key for this phone
        delete_calls = mock_redis.delete.call_args_list
        deleted_keys = [c.args[0] for c in delete_calls]
        assert any(PHONE in key for key in deleted_keys)

    @pytest.mark.asyncio
    async def test_happy_path_ack_before_pipeline(self, client, mock_services):
        """T7: PROCESSING_ACK_MESSAGE sent before extraction call."""
        await client.post("/webhook/whatsapp", data=_form_data())

        # ACK must be the first send_text_message call
        send_calls = mock_services["send_text"].call_args_list
        assert len(send_calls) >= 2  # at least ack + reply
        first_call = send_calls[0]
        assert first_call.args[0] == PHONE
        assert first_call.args[1] == PROCESSING_ACK_MESSAGE


# ===========================================================================
# T8–T13: Service argument validation and format checks
# ===========================================================================


class TestServiceArguments:
    """Verify correct arguments flow through the full HTTP → pipeline path."""

    @pytest.mark.asyncio
    async def test_request_id_threaded_to_all_services(self, client, mock_services):
        """T8: All services receive the same request_id (UUID)."""
        await client.post("/webhook/whatsapp", data=_form_data())

        # All service calls should have request_id
        extract_rid = mock_services["extract"].call_args.kwargs["request_id"]
        enrich_rid = mock_services["enrich"].call_args.kwargs["request_id"]
        translate_rid = mock_services["translate"].call_args.kwargs["request_id"]
        audio_rid = mock_services["audio"].call_args.kwargs["request_id"]
        log_rid = mock_services["log_interaction"].call_args.kwargs["request_id"]

        # All the same UUID
        assert extract_rid == enrich_rid == translate_rid == audio_rid == log_rid
        # And it's a valid UUID format
        import uuid

        uuid.UUID(extract_rid)  # Raises if invalid

    @pytest.mark.asyncio
    async def test_extraction_receives_correct_args(self, client, mock_services):
        """T9: extract_prescription_from_bytes called with image_bytes, content_type, request_id."""
        await client.post("/webhook/whatsapp", data=_form_data())

        mock_services["extract"].assert_awaited_once()
        kwargs = mock_services["extract"].call_args.kwargs
        assert kwargs["image_bytes"] == b"fake-image-bytes"
        assert kwargs["content_type"] == "image/jpeg"
        assert "request_id" in kwargs

    @pytest.mark.asyncio
    async def test_translation_receives_glossary_context(self, client, mock_services):
        """T10: simplify_and_translate receives glossary_context from format_glossary_context."""
        await client.post("/webhook/whatsapp", data=_form_data())

        mock_services["translate"].assert_awaited_once()
        kwargs = mock_services["translate"].call_args.kwargs
        assert kwargs["glossary_context"] == "Glossary:\nParacetamol → pain and fever reducer"
        assert kwargs["language_name"] == "Hindi"
        assert kwargs["language_code"] == "hi"

    @pytest.mark.asyncio
    async def test_audio_text_formatted_for_tts(self, client, mock_services):
        """T11: generate_and_deliver_audio receives formatted audio text (no emoji)."""
        await client.post("/webhook/whatsapp", data=_form_data())

        mock_services["audio"].assert_awaited_once()
        kwargs = mock_services["audio"].call_args.kwargs
        audio_text = kwargs["text"]
        assert isinstance(audio_text, str)
        assert len(audio_text) > 0
        # No emoji in audio text (check for common emoji ranges)
        emoji_re = re.compile(
            "[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff]"
        )
        assert not emoji_re.search(audio_text)

    @pytest.mark.asyncio
    async def test_reply_within_whatsapp_limit(self, client, mock_services):
        """T12: Formatted reply text ≤ 1600 chars."""
        await client.post("/webhook/whatsapp", data=_form_data())

        send_calls = mock_services["send_text"].call_args_list
        reply_calls = [c for c in send_calls if c.args[1] != PROCESSING_ACK_MESSAGE]
        assert len(reply_calls) >= 1
        reply_text = reply_calls[0].args[1]
        assert len(reply_text) <= 1600

    @pytest.mark.asyncio
    async def test_audio_text_within_tts_limit(self, client, mock_services):
        """T13: Formatted audio text ≤ 2000 chars."""
        await client.post("/webhook/whatsapp", data=_form_data())

        kwargs = mock_services["audio"].call_args.kwargs
        audio_text = kwargs["text"]
        assert len(audio_text) <= 2000


# ===========================================================================
# T14–T17: Error paths through HTTP
# ===========================================================================


class TestErrorPaths:
    """Pipeline errors through the full HTTP endpoint."""

    @pytest.mark.asyncio
    async def test_not_medical_doc_error_sends_message(self, client, mock_services):
        """T14: NotMedicalDocumentError → correct error message sent."""
        from backend.app.services.extraction import NotMedicalDocumentError

        mock_services["extract"].side_effect = NotMedicalDocumentError("not medical")

        await client.post("/webhook/whatsapp", data=_form_data())

        # Find the error message send call (not the ack)
        send_calls = mock_services["send_text"].call_args_list
        error_calls = [c for c in send_calls if c.args[1] == NOT_MEDICAL_DOC_MESSAGE]
        assert len(error_calls) == 1

    @pytest.mark.asyncio
    async def test_image_not_readable_error_sends_message(self, client, mock_services):
        """T15: ImageNotReadableError → correct error message sent."""
        from backend.app.services.extraction import ImageNotReadableError

        mock_services["extract"].side_effect = ImageNotReadableError("blurry")

        await client.post("/webhook/whatsapp", data=_form_data())

        send_calls = mock_services["send_text"].call_args_list
        error_calls = [c for c in send_calls if c.args[1] == IMAGE_NOT_READABLE_MESSAGE]
        assert len(error_calls) == 1

    @pytest.mark.asyncio
    async def test_translation_error_sends_message(self, client, mock_services):
        """T16: TranslationError → correct error message sent."""
        from backend.app.services.translation import TranslationError

        mock_services["translate"].side_effect = TranslationError("translation failed")

        await client.post("/webhook/whatsapp", data=_form_data())

        send_calls = mock_services["send_text"].call_args_list
        error_calls = [c for c in send_calls if c.args[1] == TRANSLATION_ERROR_MESSAGE]
        assert len(error_calls) == 1

    @pytest.mark.asyncio
    async def test_generic_error_sends_message(self, client, mock_services):
        """T17: RuntimeError → generic error message sent."""
        mock_services["extract"].side_effect = RuntimeError("something broke")

        await client.post("/webhook/whatsapp", data=_form_data())

        send_calls = mock_services["send_text"].call_args_list
        error_calls = [c for c in send_calls if c.args[1] == GENERIC_PIPELINE_ERROR_MESSAGE]
        assert len(error_calls) == 1


# ===========================================================================
# T18–T20: Error logging, audio fallback, session cleanup on error
# ===========================================================================


class TestErrorHandlingDetails:
    """Error logging, audio fallback, and session cleanup."""

    @pytest.mark.asyncio
    async def test_error_logs_interaction_with_error_status(self, client, mock_services):
        """T18: Error → interaction logged with status=ERROR + error_code."""
        from backend.app.db.models import InteractionStatus
        from backend.app.services.extraction import NotMedicalDocumentError

        mock_services["extract"].side_effect = NotMedicalDocumentError("not medical")

        await client.post("/webhook/whatsapp", data=_form_data())

        mock_services["log_interaction"].assert_awaited_once()
        kwargs = mock_services["log_interaction"].call_args.kwargs
        assert kwargs["status"] == InteractionStatus.ERROR
        assert kwargs["error_code"] == "NotMedicalDocumentError"
        assert isinstance(kwargs["latency_ms"], int)

    @pytest.mark.asyncio
    async def test_audio_none_skips_audio_send(self, client, mock_services):
        """T19: TTS returns None → no audio send, text still sent, status=SUCCESS."""
        from backend.app.db.models import InteractionStatus

        mock_services["audio"].return_value = None

        await client.post("/webhook/whatsapp", data=_form_data())

        # Audio send should NOT be called
        mock_services["send_audio_fallback"].assert_not_awaited()

        # Text reply should still be sent
        send_calls = mock_services["send_text"].call_args_list
        reply_calls = [c for c in send_calls if c.args[1] != PROCESSING_ACK_MESSAGE]
        assert len(reply_calls) >= 1

        # Should log as SUCCESS
        kwargs = mock_services["log_interaction"].call_args.kwargs
        assert kwargs["status"] == InteractionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_error_still_cleans_session(self, client, mock_services):
        """T20: Pipeline error → session still deleted from Redis."""
        from backend.app.services.extraction import ExtractionError

        mock_services["extract"].side_effect = ExtractionError("fail")

        await client.post("/webhook/whatsapp", data=_form_data())

        mock_redis = mock_services["redis"]
        mock_redis.delete.assert_called()
        delete_calls = mock_redis.delete.call_args_list
        deleted_keys = [c.args[0] for c in delete_calls]
        assert any(PHONE in key for key in deleted_keys)
