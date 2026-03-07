"""S13.1 — Hindi End-to-End Smoke Test.

20 tests simulating the full Hindi conversation flow through the HTTP webhook:
  Step 1: New user → welcome message + language selection
  Step 2: Hindi selection ("1" / "Hindi" / "hi") → image prompt
  Step 3: Image upload → ack + pipeline → text reply + audio delivery
  Step 4: Backend verification — extraction, glossary, drug lookup, logging, cleanup

All external services mocked. Uses httpx.AsyncClient + ASGITransport for HTTP-level tests.
"""

from __future__ import annotations

import asyncio
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
    IMAGE_PROMPT_MESSAGE,
    PROCESSING_ACK_MESSAGE,
    WELCOME_MESSAGE,
)
from backend.app.core.security import validate_twilio_signature  # noqa: E402
from backend.app.db.redis import get_redis  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.models.schemas import (  # noqa: E402
    DrugInfo,
    GlossaryEntry,
    MedicineEntry,
    PrescriptionData,
    SessionStatus,
    TranslationResult,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PHONE = "whatsapp:+919876543210"
MEDIA_URL = "https://api.twilio.com/media/test-prescription.jpg"
AUDIO_URL = "https://s3.ap-south-1.amazonaws.com/audio/test-hindi.ogg"


# ---------------------------------------------------------------------------
# Test data builders — Hindi-specific
# ---------------------------------------------------------------------------


def _make_hindi_prescription() -> PrescriptionData:
    """Prescription with common Indian medicines."""
    return PrescriptionData(
        doctor_name="Dr. Sharma",
        medicines=[
            MedicineEntry(
                medicine_name="Paracetamol",
                dosage="500mg",
                frequency="3 times a day",
                duration="5 days",
                confidence=0.95,
            ),
            MedicineEntry(
                medicine_name="Azithromycin",
                dosage="500mg",
                frequency="Once daily",
                duration="3 days",
                confidence=0.88,
            ),
            MedicineEntry(
                medicine_name="Cetirizine",
                dosage="10mg",
                frequency="Once at night",
                duration="7 days",
                confidence=0.60,  # Low confidence — should trigger warning
            ),
        ],
        overall_confidence=0.81,
    )


def _make_hindi_translation() -> TranslationResult:
    """Hindi translation result with per-medicine summaries."""
    return TranslationResult(
        translated_text=(
            "आपके प्रिस्क्रिप्शन में तीन दवाइयाँ हैं: "
            "Paracetamol बुखार और दर्द के लिए, "
            "Azithromycin संक्रमण के लिए, "
            "और Cetirizine एलर्जी के लिए।"
        ),
        per_medicine_summaries=[
            "Paracetamol: बुखार और दर्द कम करने की दवा",
            "Azithromycin: बैक्टीरिया संक्रमण के इलाज के लिए",
            "Cetirizine: एलर्जी और खुजली से राहत",
        ],
        disclaimer="यह चिकित्सा सलाह नहीं है। कृपया अपने डॉक्टर से परामर्श लें।",
        language_code="hi",
    )


def _make_hindi_drug_info_list() -> list[DrugInfo | None]:
    return [
        DrugInfo(
            brand_name="Crocin",
            generic_name="Paracetamol",
            purpose_en="Pain and fever relief",
        ),
        DrugInfo(
            brand_name="Azithral",
            generic_name="Azithromycin",
            purpose_en="Antibiotic for bacterial infections",
        ),
        DrugInfo(
            brand_name="Alerid",
            generic_name="Cetirizine",
            purpose_en="Antihistamine for allergies",
        ),
    ]


def _make_hindi_glossary_entries() -> list[GlossaryEntry]:
    return [
        GlossaryEntry(
            term="Paracetamol",
            explanation="pain and fever reducer",
            vernacular="दर्द और बुखार कम करने वाली दवा",
        ),
        GlossaryEntry(
            term="antibiotic",
            explanation="medicine that kills bacteria",
            vernacular="जीवाणुरोधी दवा",
        ),
    ]


def _waiting_for_language_session_json() -> str:
    """Session JSON for WAITING_FOR_LANGUAGE state."""
    return json.dumps(
        {
            "status": SessionStatus.WAITING_FOR_LANGUAGE.value,
            "language_code": None,
            "language_name": None,
            "request_id": "req-welcome-123",
            "created_at": "2026-03-05T10:00:00Z",
        }
    )


def _waiting_for_image_hindi_session_json() -> str:
    """Session JSON for WAITING_FOR_IMAGE state with Hindi selected."""
    return json.dumps(
        {
            "status": SessionStatus.WAITING_FOR_IMAGE.value,
            "language_code": "hi",
            "language_name": "Hindi",
            "request_id": "req-hindi-456",
            "created_at": "2026-03-05T10:00:00Z",
        }
    )


IMAGE_FORM_DATA = {
    "From": PHONE,
    "Body": "",
    "NumMedia": "1",
    "MediaUrl0": MEDIA_URL,
    "MediaContentType0": "image/jpeg",
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_mock_redis(session_json: str | None = None) -> AsyncMock:
    """Create a mock Redis that returns the given session JSON for any GET."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=session_json)
    mock_redis.set = AsyncMock()
    mock_redis.delete = AsyncMock()
    return mock_redis


def _build_app(mock_redis: AsyncMock) -> object:
    """Create a test app with HMAC bypass and mocked Redis."""
    app = create_app()
    app.dependency_overrides[validate_twilio_signature] = lambda: None

    async def _mock_redis_dep():
        yield mock_redis

    app.dependency_overrides[get_redis] = _mock_redis_dep
    return app


# ---------------------------------------------------------------------------
# Pipeline service mocking (shared by T9–T20)
# ---------------------------------------------------------------------------


@pytest.fixture
def hindi_pipeline_mocks():
    """Patch all pipeline services with Hindi-specific test data."""
    prescription = _make_hindi_prescription()
    drug_info_list = _make_hindi_drug_info_list()
    glossary_entries = _make_hindi_glossary_entries()
    translation_result = _make_hindi_translation()

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
            return_value="Glossary:\nParacetamol → दर्द और बुखार कम करने वाली दवा",
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

    # Mock AsyncSessionLocal
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

    mocks["prescription"] = prescription
    mocks["translation_result"] = translation_result

    yield mocks

    for p in entered:
        p.stop()


@pytest.fixture
def hindi_pipeline_client(hindi_pipeline_mocks):
    """Provide (client, mocks) tuple for pipeline tests."""
    mock_redis = _make_mock_redis(session_json=_waiting_for_image_hindi_session_json())
    hindi_pipeline_mocks["redis"] = mock_redis
    app = _build_app(mock_redis)

    async def _make_client():
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    return _make_client, hindi_pipeline_mocks, app


# ===========================================================================
# T1: File exists
# ===========================================================================


def test_e2e_test_file_exists():
    """T1: test_s13_1_hindi_e2e_test.py exists in backend/tests/."""
    path = Path(__file__)
    assert path.name == "test_s13_1_hindi_e2e_test.py"
    assert path.parent.name == "tests"
    assert path.exists()


# ===========================================================================
# T2–T4: Step 1 — Welcome state (new user, no session in Redis)
# ===========================================================================


class TestWelcomeStep:
    """New user sends first message → welcome + language selection."""

    @pytest.fixture
    def mock_redis_no_session(self):
        return _make_mock_redis(session_json=None)

    @pytest.fixture
    def welcome_app(self, mock_redis_no_session):
        app = _build_app(mock_redis_no_session)
        yield app
        app.dependency_overrides.clear()

    @pytest.fixture
    async def welcome_client(self, welcome_app):
        transport = ASGITransport(app=welcome_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_welcome_message_sent(self, welcome_client, mock_redis_no_session):
        """T2: New user → welcome message with consent text."""
        with (
            patch(
                "backend.app.api.webhooks.send_text_message", new_callable=AsyncMock
            ) as mock_send,
            patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
        ):
            resp = await welcome_client.post(
                "/webhook/whatsapp", data={"From": PHONE, "Body": "Start"}
            )
            assert resp.status_code == 200

            calls = mock_send.call_args_list
            assert len(calls) >= 1
            assert calls[0].args[0] == PHONE
            assert calls[0].args[1] == WELCOME_MESSAGE

    @pytest.mark.asyncio
    async def test_language_selection_sent(self, welcome_client, mock_redis_no_session):
        """T3: After welcome, language selection menu sent."""
        with (
            patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
            patch(
                "backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock
            ) as mock_lang,
        ):
            await welcome_client.post("/webhook/whatsapp", data={"From": PHONE, "Body": "Start"})
            mock_lang.assert_awaited_once_with(PHONE)

    @pytest.mark.asyncio
    async def test_session_created_waiting_for_language(
        self, welcome_client, mock_redis_no_session
    ):
        """T4: Session created in Redis with status=WAITING_FOR_LANGUAGE."""
        with (
            patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock),
            patch("backend.app.api.webhooks.send_language_selection", new_callable=AsyncMock),
        ):
            await welcome_client.post("/webhook/whatsapp", data={"From": PHONE, "Body": "Start"})

            set_calls = mock_redis_no_session.set.call_args_list
            assert len(set_calls) >= 1
            saved_json = json.loads(set_calls[0].args[1])
            assert saved_json["status"] == SessionStatus.WAITING_FOR_LANGUAGE.value


# ===========================================================================
# T5–T8: Step 2 — Language selection (Hindi via "1", "Hindi", "hi")
# ===========================================================================


class TestHindiLanguageSelection:
    """User selects Hindi → image prompt."""

    @pytest.fixture
    def mock_redis_waiting_language(self):
        return _make_mock_redis(session_json=_waiting_for_language_session_json())

    @pytest.fixture
    def lang_app(self, mock_redis_waiting_language):
        app = _build_app(mock_redis_waiting_language)
        yield app
        app.dependency_overrides.clear()

    @pytest.fixture
    async def lang_client(self, lang_app):
        transport = ASGITransport(app=lang_app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_hindi_via_number_1(self, lang_client, mock_redis_waiting_language):
        """T5: Reply '1' selects Hindi, image prompt sent."""
        with patch(
            "backend.app.api.webhooks.send_text_message", new_callable=AsyncMock
        ) as mock_send:
            resp = await lang_client.post("/webhook/whatsapp", data={"From": PHONE, "Body": "1"})
            assert resp.status_code == 200

            send_calls = mock_send.call_args_list
            prompt_calls = [c for c in send_calls if c.args[1] == IMAGE_PROMPT_MESSAGE]
            assert len(prompt_calls) == 1

    @pytest.mark.asyncio
    async def test_hindi_via_name(self, lang_client, mock_redis_waiting_language):
        """T6: Reply 'Hindi' selects Hindi, image prompt sent."""
        with patch(
            "backend.app.api.webhooks.send_text_message", new_callable=AsyncMock
        ) as mock_send:
            await lang_client.post("/webhook/whatsapp", data={"From": PHONE, "Body": "Hindi"})
            send_calls = mock_send.call_args_list
            prompt_calls = [c for c in send_calls if c.args[1] == IMAGE_PROMPT_MESSAGE]
            assert len(prompt_calls) == 1

    @pytest.mark.asyncio
    async def test_hindi_via_code(self, lang_client, mock_redis_waiting_language):
        """T7: Reply 'hi' selects Hindi, image prompt sent."""
        with patch(
            "backend.app.api.webhooks.send_text_message", new_callable=AsyncMock
        ) as mock_send:
            await lang_client.post("/webhook/whatsapp", data={"From": PHONE, "Body": "hi"})
            send_calls = mock_send.call_args_list
            prompt_calls = [c for c in send_calls if c.args[1] == IMAGE_PROMPT_MESSAGE]
            assert len(prompt_calls) == 1

    @pytest.mark.asyncio
    async def test_session_updated_to_waiting_for_image(
        self, lang_client, mock_redis_waiting_language
    ):
        """T8: Session updated: language_code='hi', language_name='Hindi', WAITING_FOR_IMAGE."""
        with patch("backend.app.api.webhooks.send_text_message", new_callable=AsyncMock):
            await lang_client.post("/webhook/whatsapp", data={"From": PHONE, "Body": "1"})

            set_calls = mock_redis_waiting_language.set.call_args_list
            assert len(set_calls) >= 1
            saved_json = json.loads(set_calls[0].args[1])
            assert saved_json["status"] == SessionStatus.WAITING_FOR_IMAGE.value
            assert saved_json["language_code"] == "hi"
            assert saved_json["language_name"] == "Hindi"


# ===========================================================================
# T9–T14: Step 3 — Image upload + pipeline (Hindi output)
# ===========================================================================


class TestHindiPipelineOutput:
    """Image sent with Hindi session → full pipeline → correct output."""

    @pytest.mark.asyncio
    async def test_ack_sent_before_pipeline(self, hindi_pipeline_client):
        """T9: Processing acknowledgement sent immediately after image received."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        send_calls = mocks["send_text"].call_args_list
        assert len(send_calls) >= 1
        assert send_calls[0].args[0] == PHONE
        assert send_calls[0].args[1] == PROCESSING_ACK_MESSAGE
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_text_reply_contains_english_medicine_names(self, hindi_pipeline_client):
        """T10: Text reply preserves medicine names in English."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        send_calls = mocks["send_text"].call_args_list
        reply_calls = [c for c in send_calls if c.args[1] != PROCESSING_ACK_MESSAGE]
        assert len(reply_calls) >= 1
        reply_text = reply_calls[0].args[1]
        assert "Paracetamol" in reply_text
        assert "Azithromycin" in reply_text
        assert "Cetirizine" in reply_text
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_text_reply_includes_hindi_disclaimer(self, hindi_pipeline_client):
        """T11: Hindi disclaimer present in text reply."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        send_calls = mocks["send_text"].call_args_list
        reply_calls = [c for c in send_calls if c.args[1] != PROCESSING_ACK_MESSAGE]
        assert len(reply_calls) >= 1
        assert mocks["translation_result"].disclaimer in reply_calls[0].args[1]
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_text_reply_within_whatsapp_limit(self, hindi_pipeline_client):
        """T12: Reply text <= 1600 chars (WhatsApp limit)."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        send_calls = mocks["send_text"].call_args_list
        reply_calls = [c for c in send_calls if c.args[1] != PROCESSING_ACK_MESSAGE]
        assert len(reply_calls) >= 1
        assert len(reply_calls[0].args[1]) <= 1600
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_audio_message_sent(self, hindi_pipeline_client):
        """T13: Hindi audio message sent with presigned URL."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        mocks["send_audio_fallback"].assert_awaited_once()
        call_args = mocks["send_audio_fallback"].call_args
        assert call_args.args[0] == PHONE
        assert call_args.args[1] == AUDIO_URL
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_audio_text_no_emoji_or_markdown(self, hindi_pipeline_client):
        """T14: Audio text is speech-friendly — no emoji, no markdown."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        audio_text = mocks["audio"].call_args.kwargs["text"]
        assert isinstance(audio_text, str)
        assert len(audio_text) > 0
        emoji_re = re.compile(
            "[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff]"
        )
        assert not emoji_re.search(audio_text)
        assert "**" not in audio_text
        assert not re.search(r"^#+\s", audio_text, re.MULTILINE)
        app.dependency_overrides.clear()


# ===========================================================================
# T15–T18: Backend verification — service arguments (Hindi-specific)
# ===========================================================================


class TestHindiServiceArguments:
    """Verify Hindi-specific arguments flow through the pipeline."""

    @pytest.mark.asyncio
    async def test_extraction_receives_image_url(self, hindi_pipeline_client):
        """T15: extract_prescription_from_bytes called with downloaded image bytes."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        mocks["extract"].assert_awaited_once()
        kwargs = mocks["extract"].call_args.kwargs
        assert kwargs["image_bytes"] == b"fake-image-bytes"
        assert kwargs["content_type"] == "image/jpeg"
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_translation_receives_hindi_language(self, hindi_pipeline_client):
        """T16: simplify_and_translate receives language_name='Hindi', language_code='hi'."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        kwargs = mocks["translate"].call_args.kwargs
        assert kwargs["language_name"] == "Hindi"
        assert kwargs["language_code"] == "hi"
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_glossary_lookup_uses_hindi_code(self, hindi_pipeline_client):
        """T17: lookup_terms called with language_code='hi'."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        mocks["lookup"].assert_awaited_once()
        assert mocks["lookup"].call_args.args[1] == "hi"
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_tts_audio_receives_hindi_code(self, hindi_pipeline_client):
        """T18: generate_and_deliver_audio receives language_code='hi'."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        assert mocks["audio"].call_args.kwargs["language_code"] == "hi"
        app.dependency_overrides.clear()


# ===========================================================================
# T19–T20: Interaction logging + session cleanup
# ===========================================================================


class TestHindiLoggingAndCleanup:
    """Verify interaction log and session cleanup for Hindi flow."""

    @pytest.mark.asyncio
    async def test_interaction_logged_hindi_success_no_phi(self, hindi_pipeline_client):
        """T19: Interaction logged: language_code='hi', status=SUCCESS, no PHI."""
        from backend.app.db.models import InteractionStatus

        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        mocks["log_interaction"].assert_awaited_once()
        kwargs = mocks["log_interaction"].call_args.kwargs
        assert kwargs["status"] == InteractionStatus.SUCCESS
        assert kwargs["language_code"] == "hi"
        assert isinstance(kwargs["latency_ms"], int)
        assert kwargs["latency_ms"] >= 0
        # Confidence: (0.95 + 0.88 + 0.60) / 3 ≈ 0.81
        assert kwargs["confidence_avg"] is not None
        assert abs(kwargs["confidence_avg"] - 0.81) < 0.01
        # No PHI stored: phone_number is passed for hashing inside _log_interaction
        assert kwargs["phone_number"] == PHONE
        assert "image_url" not in kwargs
        assert "extracted_text" not in kwargs
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_session_deleted_after_pipeline(self, hindi_pipeline_client):
        """T20: Redis session cleaned up after successful pipeline completion."""
        make_client, mocks, app = hindi_pipeline_client
        async with await make_client() as client:
            await client.post("/webhook/whatsapp", data=IMAGE_FORM_DATA)
            await asyncio.sleep(0)  # let background pipeline task run

        mock_redis = mocks["redis"]
        mock_redis.delete.assert_called()
        deleted_keys = [c.args[0] for c in mock_redis.delete.call_args_list]
        assert any(PHONE in key for key in deleted_keys)
        app.dependency_overrides.clear()
