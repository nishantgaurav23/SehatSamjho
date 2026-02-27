"""Tests for app/api/webhooks.py

Tests the WhatsApp webhook state machine using FakeRedis and mocked external
services (Twilio, OpenAI). No real network calls are made.

Strategy:
    - FakeRedis: in-memory dict replacing Redis for session state
    - override_get_redis / override_get_db: FastAPI dependency overrides
    - mocker.patch: replaces send_text_message, send_language_selection,
      and extract_prescription so no real APIs are called

Run:
    cd backend
    pytest tests/api/test_webhooks.py -v
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.webhooks import _SESSION_PREFIX
from app.core.security import hash_phone
from app.db.database import AsyncSessionLocal, get_db
from app.db.redis import get_redis
from app.main import app
from app.models.schemas import ConversationState, UserSession


# ── FakeRedis ─────────────────────────────────────────────────────────────────

class FakeRedis:
    """In-memory Redis substitute for testing session state."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def aclose(self) -> None:
        pass


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
async def webhook_client(fake_redis: FakeRedis, mocker) -> AsyncGenerator:
    """AsyncClient with all external dependencies replaced by test doubles.

    - get_redis  → FakeRedis (in-memory dict)
    - get_db     → non-committing AsyncSession (test data never written)
    - send_text_message / send_language_selection → AsyncMock (no Twilio calls)
    """
    # Prevent actual Twilio calls for any test using this fixture
    mocker.patch(
        "app.api.webhooks.send_text_message",
        new=AsyncMock(return_value="SM_fixture_mock"),
    )
    mocker.patch(
        "app.api.webhooks.send_language_selection",
        new=AsyncMock(return_value="SM_fixture_mock"),
    )

    async def override_get_redis() -> AsyncGenerator:
        yield fake_redis

    async def override_get_db() -> AsyncGenerator:
        async with AsyncSessionLocal() as session:
            yield session
            # intentionally no commit — auto-rolled back on close

    app.dependency_overrides[get_redis] = override_get_redis
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_form(
    body: str = "",
    num_media: int = 0,
    media_url: str | None = None,
    message_sid: str = "SM_test_webhook_sid",
) -> dict:
    """Build a minimal Twilio webhook form payload."""
    data = {
        "From": "whatsapp:+919876543210",
        "To": "whatsapp:+14155238886",
        "Body": body,
        "NumMedia": str(num_media),
        "MessageSid": message_sid,
    }
    if media_url:
        data["MediaUrl0"] = media_url
        data["MediaContentType0"] = "image/jpeg"
    return data


async def _set_session(fake_redis: FakeRedis, state: ConversationState, **kwargs) -> UserSession:
    """Inject a pre-built session into FakeRedis before a test runs."""
    phone_hash = hash_phone("whatsapp:+919876543210")
    session = UserSession(state=state, **kwargs)
    await fake_redis.setex(
        f"{_SESSION_PREFIX}{phone_hash}",
        1800,
        session.model_dump_json(),
    )
    return session


async def _read_session(fake_redis: FakeRedis) -> UserSession | None:
    """Read the current session from FakeRedis (for assertion in tests)."""
    phone_hash = hash_phone("whatsapp:+919876543210")
    raw = await fake_redis.get(f"{_SESSION_PREFIX}{phone_hash}")
    if raw is None:
        return None
    return UserSession.model_validate_json(raw)


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_new_user_unrecognized_message_gets_language_menu(webhook_client, mocker):
    """New user (no existing session) with unrecognized message → language menu sent.

    Note: 'Hi' lowercases to 'hi' which matches the Hindi language code, so
    we use 'Start' (no language match) to test the unknown-input path.
    """
    send_lang_mock = mocker.patch(
        "app.api.webhooks.send_language_selection",
        new=AsyncMock(return_value="SM_mock"),
    )

    resp = await webhook_client.post("/webhook/whatsapp", data=_make_form("Start"))

    assert resp.status_code == 200
    send_lang_mock.assert_called_once()


async def test_valid_language_number_transitions_state(webhook_client, fake_redis, mocker):
    """User replies '1' (Hindi) → session transitions to WAITING_FOR_IMAGE."""
    mocker.patch(
        "app.api.webhooks.send_text_message",
        new=AsyncMock(return_value="SM_mock"),
    )

    resp = await webhook_client.post("/webhook/whatsapp", data=_make_form("1"))

    assert resp.status_code == 200
    session = await _read_session(fake_redis)
    assert session is not None
    assert session.state == ConversationState.WAITING_FOR_IMAGE
    assert session.language_code == "hi"  # position 1 = Hindi


async def test_invalid_language_resends_menu(webhook_client, mocker):
    """User sends unrecognized text → language menu is resent."""
    send_lang_mock = mocker.patch(
        "app.api.webhooks.send_language_selection",
        new=AsyncMock(return_value="SM_mock"),
    )

    resp = await webhook_client.post(
        "/webhook/whatsapp", data=_make_form("hello world")
    )

    assert resp.status_code == 200
    send_lang_mock.assert_called_once()


async def test_text_when_expecting_image(webhook_client, fake_redis, mocker):
    """User sends text in WAITING_FOR_IMAGE state → 'please send photo' reply."""
    await _set_session(
        fake_redis,
        ConversationState.WAITING_FOR_IMAGE,
        language_code="hi",
        language_name="Hindi",
    )
    send_mock = mocker.patch(
        "app.api.webhooks.send_text_message",
        new=AsyncMock(return_value="SM_mock"),
    )

    resp = await webhook_client.post(
        "/webhook/whatsapp", data=_make_form("what is this?")
    )

    assert resp.status_code == 200
    send_mock.assert_called_once()
    body = send_mock.call_args[0][1]  # second positional arg = message body
    assert "photo" in body.lower()


async def test_image_triggers_extraction_and_response(webhook_client, fake_redis, mocker):
    """User sends image → extract_prescription called, reply sent, state=DONE."""
    await _set_session(
        fake_redis,
        ConversationState.WAITING_FOR_IMAGE,
        language_code="hi",
        language_name="Hindi",
    )

    from app.models.schemas import DocumentType, Medication, PrescriptionData

    mock_prescription = PrescriptionData(
        doc_type=DocumentType.PRESCRIPTION,
        medications=[Medication(name="Metformin", dosage="500mg")],
        diagnosis="Diabetes",
    )
    extract_mock = mocker.patch(
        "app.api.webhooks.extract_prescription",
        new=AsyncMock(return_value=(mock_prescription, 0.9)),
    )
    send_mock = mocker.patch(
        "app.api.webhooks.send_text_message",
        new=AsyncMock(return_value="SM_mock"),
    )

    resp = await webhook_client.post(
        "/webhook/whatsapp",
        data=_make_form(num_media=1, media_url="http://api.twilio.com/media/SM_img"),
    )

    assert resp.status_code == 200
    extract_mock.assert_called_once()
    # At least 2 sends: "processing..." + the extraction result
    assert send_mock.call_count >= 2

    session = await _read_session(fake_redis)
    assert session.state == ConversationState.DONE


async def test_not_medical_document_error_handling(webhook_client, fake_redis, mocker):
    """NotMedicalDocumentError → error msg sent, state reset to WAITING_FOR_IMAGE."""
    await _set_session(
        fake_redis,
        ConversationState.WAITING_FOR_IMAGE,
        language_code="hi",
        language_name="Hindi",
    )

    from app.services.extraction import NotMedicalDocumentError

    mocker.patch(
        "app.api.webhooks.extract_prescription",
        new=AsyncMock(side_effect=NotMedicalDocumentError("not medical")),
    )
    mocker.patch(
        "app.api.webhooks.send_text_message",
        new=AsyncMock(return_value="SM_mock"),
    )

    resp = await webhook_client.post(
        "/webhook/whatsapp",
        data=_make_form(num_media=1, media_url="http://api.twilio.com/media/SM_img"),
    )

    assert resp.status_code == 200
    session = await _read_session(fake_redis)
    assert session.state == ConversationState.WAITING_FOR_IMAGE


async def test_unreadable_image_error_handling(webhook_client, fake_redis, mocker):
    """ImageNotReadableError → helpful photo-quality message sent."""
    await _set_session(
        fake_redis,
        ConversationState.WAITING_FOR_IMAGE,
        language_code="en",
        language_name="English",
    )

    from app.services.extraction import ImageNotReadableError

    mocker.patch(
        "app.api.webhooks.extract_prescription",
        new=AsyncMock(side_effect=ImageNotReadableError("blurry")),
    )
    send_mock = mocker.patch(
        "app.api.webhooks.send_text_message",
        new=AsyncMock(return_value="SM_mock"),
    )

    resp = await webhook_client.post(
        "/webhook/whatsapp",
        data=_make_form(num_media=1, media_url="http://api.twilio.com/media/SM_img"),
    )

    assert resp.status_code == 200
    # 2 sends: "processing..." + the image-quality error message
    assert send_mock.call_count >= 2
    last_body = send_mock.call_args_list[-1][0][1]
    assert any(
        word in last_body.lower()
        for word in ("blurry", "photo", "lighting", "unclear")
    )


async def test_processing_state_blocks_new_request(webhook_client, fake_redis, mocker):
    """User in PROCESSING state → 'still processing' message, no extraction."""
    await _set_session(
        fake_redis,
        ConversationState.PROCESSING,
        language_code="hi",
        language_name="Hindi",
    )
    send_mock = mocker.patch(
        "app.api.webhooks.send_text_message",
        new=AsyncMock(return_value="SM_mock"),
    )

    resp = await webhook_client.post(
        "/webhook/whatsapp", data=_make_form("anything")
    )

    assert resp.status_code == 200
    send_mock.assert_called_once()
    body = send_mock.call_args[0][1]
    assert "processing" in body.lower() or "wait" in body.lower()
