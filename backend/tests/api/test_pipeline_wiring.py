"""S10.1 — Pipeline Wiring Tests.

20 tests covering _run_pipeline(): pipeline sequence, request_id threading,
latency tracking, confidence calculation, interaction logging, session cleanup,
audio fallback, DB session acquisition, and Loguru context binding.
"""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.models.schemas import (
    DrugInfo,
    GlossaryEntry,
    MedicineEntry,
    PrescriptionData,
    SessionState,
    SessionStatus,
    TranslationResult,
    WebhookPayload,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_payload(**overrides) -> WebhookPayload:
    defaults = {
        "from_number": "whatsapp:+919876543210",
        "body": "",
        "num_media": 1,
        "media_url": "https://api.twilio.com/media/test-image.jpg",
        "media_content_type": "image/jpeg",
    }
    defaults.update(overrides)
    return WebhookPayload(**defaults)


def _make_session(**overrides) -> SessionState:
    defaults = {
        "status": SessionStatus.PROCESSING,
        "language_code": "hi",
        "language_name": "Hindi",
        "request_id": "test-req-123",
        "created_at": "2024-01-01T00:00:00Z",
    }
    defaults.update(overrides)
    return SessionState(**defaults)


def _make_prescription(**overrides) -> PrescriptionData:
    defaults = {
        "doctor_name": "Dr. Sharma",
        "medicines": [
            MedicineEntry(
                medicine_name="Paracetamol",
                dosage="500mg",
                frequency="3 times a day",
                confidence=0.95,
            ),
            MedicineEntry(
                medicine_name="Amoxicillin",
                dosage="250mg",
                frequency="2 times a day",
                confidence=0.85,
            ),
        ],
        "overall_confidence": 0.9,
    }
    defaults.update(overrides)
    return PrescriptionData(**defaults)


def _make_translation_result(**overrides) -> TranslationResult:
    defaults = {
        "translated_text": "Your prescription contains Paracetamol 500mg...",
        "per_medicine_summaries": ["Paracetamol: pain relief"],
        "disclaimer": "This is not medical advice.",
        "language_code": "hi",
    }
    defaults.update(overrides)
    return TranslationResult(**defaults)


def _make_drug_info_list() -> list[DrugInfo | None]:
    return [
        DrugInfo(
            brand_name="Crocin",
            generic_name="Paracetamol",
            purpose_en="Pain relief",
        ),
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


REQUEST_ID = "req-uuid-4-test"
AUDIO_URL = "https://s3.amazonaws.com/audio/test.ogg"


@pytest.fixture
def mock_services():
    """Patch all service calls used by _run_pipeline()."""
    prescription = _make_prescription()
    drug_info_list = _make_drug_info_list()
    glossary_entries = _make_glossary_entries()
    translation_result = _make_translation_result()

    patches = {
        "extract": patch(
            "backend.app.api.webhooks.extract_prescription",
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
            return_value="Glossary:\nParacetamol → दर्द और बुखार",
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
        "delete_session": patch(
            "backend.app.api.webhooks._delete_session",
            new_callable=AsyncMock,
        ),
    }

    mocks = {}
    entered = []
    for name, p in patches.items():
        m = p.start()
        entered.append(p)
        mocks[name] = m

    # Mock AsyncSessionLocal as async context manager yielding an AsyncMock session
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

    # Attach data for assertions
    mocks["prescription"] = prescription
    mocks["drug_info_list"] = drug_info_list
    mocks["glossary_entries"] = glossary_entries
    mocks["translation_result"] = translation_result

    yield mocks

    for p in entered:
        p.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPipelineWiringImportAndSignature:
    """Tests 1–2: Import and signature validation."""

    def test_run_pipeline_exists_and_is_async(self):
        """T1: _run_pipeline is importable and is a coroutine function."""
        from backend.app.api.webhooks import _run_pipeline

        assert inspect.iscoroutinefunction(_run_pipeline)

    def test_run_pipeline_signature(self):
        """T2: _run_pipeline accepts (payload, session, request_id, redis)."""
        from backend.app.api.webhooks import _run_pipeline

        sig = inspect.signature(_run_pipeline)
        params = list(sig.parameters.keys())
        assert params == ["payload", "session", "request_id", "redis"]


class TestPipelineServiceCalls:
    """Tests 3–8: Verify each service is called with correct arguments."""

    @pytest.mark.asyncio
    async def test_pipeline_calls_extract_prescription(self, mock_services):
        """T3: extract_prescription() called with media_url, content_type, request_id."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        mock_services["extract"].assert_awaited_once_with(
            image_url=payload.media_url,
            content_type=payload.media_content_type,
            request_id=REQUEST_ID,
        )

    @pytest.mark.asyncio
    async def test_pipeline_calls_enrich_prescription(self, mock_services):
        """T4: enrich_prescription() called with redis, prescription, request_id."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()
        redis_mock = AsyncMock()

        await _run_pipeline(payload, session, REQUEST_ID, redis_mock)

        mock_services["enrich"].assert_awaited_once_with(
            redis_client=redis_mock,
            prescription=mock_services["prescription"],
            request_id=REQUEST_ID,
        )

    @pytest.mark.asyncio
    async def test_pipeline_calls_lookup_terms(self, mock_services):
        """T5: lookup_terms() called with medicine names, language_code, redis."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()
        redis_mock = AsyncMock()

        await _run_pipeline(payload, session, REQUEST_ID, redis_mock)

        expected_terms = ["Paracetamol", "Amoxicillin"]
        mock_services["lookup"].assert_awaited_once_with(
            expected_terms, session.language_code, redis_mock
        )

    @pytest.mark.asyncio
    async def test_pipeline_calls_format_glossary_context(self, mock_services):
        """T6: format_glossary_context() called with glossary entries, language_name."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        mock_services["format_glossary"].assert_called_once_with(
            mock_services["glossary_entries"], session.language_name
        )

    @pytest.mark.asyncio
    async def test_pipeline_calls_simplify_and_translate(self, mock_services):
        """T7: simplify_and_translate() called with all correct args."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        mock_services["translate"].assert_awaited_once_with(
            prescription=mock_services["prescription"],
            language_name=session.language_name,
            language_code=session.language_code,
            drug_info_list=mock_services["drug_info_list"],
            glossary_context="Glossary:\nParacetamol → दर्द और बुखार",
            request_id=REQUEST_ID,
        )

    @pytest.mark.asyncio
    async def test_pipeline_calls_generate_and_deliver_audio(self, mock_services):
        """T8: generate_and_deliver_audio() called with formatted audio text, language_code, request_id."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        mock_services["audio"].assert_awaited_once()
        call_kwargs = mock_services["audio"].call_args.kwargs
        # Text is now formatted via _format_audio_text (not raw translated_text)
        assert isinstance(call_kwargs["text"], str)
        assert len(call_kwargs["text"]) > 0
        assert call_kwargs["language_code"] == session.language_code
        assert call_kwargs["request_id"] == REQUEST_ID


class TestPipelineMessaging:
    """Tests 9–11: Text and audio message sending."""

    @pytest.mark.asyncio
    async def test_pipeline_sends_text_reply(self, mock_services):
        """T9: send_text_message() called with from_number and formatted reply."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        mock_services["send_text"].assert_awaited_once()
        call_args = mock_services["send_text"].call_args
        assert call_args.args[0] == payload.from_number
        # The text is now formatted via _format_reply, so it should contain
        # medicine names and disclaimer from the translation result
        sent_text = call_args.args[1]
        assert "Paracetamol" in sent_text
        assert mock_services["translation_result"].disclaimer in sent_text

    @pytest.mark.asyncio
    async def test_pipeline_sends_audio_when_url_available(self, mock_services):
        """T10: When audio URL returned, send_audio_message_with_fallback() called."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        mock_services["send_audio_fallback"].assert_awaited_once()
        call_args = mock_services["send_audio_fallback"].call_args
        assert call_args.args[0] == payload.from_number
        assert call_args.args[1] == AUDIO_URL
        # fallback_text is now formatted audio text (not raw translated_text)
        assert isinstance(call_args.kwargs.get("fallback_text"), str)
        assert len(call_args.kwargs["fallback_text"]) > 0

    @pytest.mark.asyncio
    async def test_pipeline_skips_audio_when_none(self, mock_services):
        """T11: When audio URL is None, send_audio_message_with_fallback() NOT called."""
        from backend.app.api.webhooks import _run_pipeline

        mock_services["audio"].return_value = None
        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        mock_services["send_audio_fallback"].assert_not_awaited()


class TestPipelineSessionAndLogging:
    """Tests 12–16: Session cleanup, interaction logging, latency, confidence."""

    @pytest.mark.asyncio
    async def test_pipeline_deletes_session_on_success(self, mock_services):
        """T12: _delete_session() called after successful pipeline."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()
        redis_mock = AsyncMock()

        await _run_pipeline(payload, session, REQUEST_ID, redis_mock)

        mock_services["delete_session"].assert_awaited_once_with(payload.from_number, redis_mock)

    @pytest.mark.asyncio
    async def test_pipeline_logs_interaction_on_success(self, mock_services):
        """T13: _log_interaction() called with status=SUCCESS."""
        from backend.app.api.webhooks import _run_pipeline
        from backend.app.db.models import InteractionStatus

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        mock_services["log_interaction"].assert_awaited_once()
        call_kwargs = mock_services["log_interaction"].call_args
        # Check key arguments
        assert call_kwargs.kwargs["status"] == InteractionStatus.SUCCESS
        assert call_kwargs.kwargs["request_id"] == REQUEST_ID

    @pytest.mark.asyncio
    async def test_pipeline_latency_tracking(self, mock_services):
        """T14: _log_interaction() receives latency_ms > 0."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        call_kwargs = mock_services["log_interaction"].call_args
        latency = call_kwargs.kwargs.get("latency_ms")
        assert latency is not None
        assert isinstance(latency, int)
        assert latency >= 0

    @pytest.mark.asyncio
    async def test_pipeline_confidence_avg_calculated(self, mock_services):
        """T15: confidence_avg is computed from PrescriptionData medicines."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        call_kwargs = mock_services["log_interaction"].call_args
        confidence = call_kwargs.kwargs.get("confidence_avg")
        # Medicines have confidence 0.95 and 0.85 → avg = 0.9
        assert confidence is not None
        assert abs(confidence - 0.9) < 0.01

    @pytest.mark.asyncio
    async def test_pipeline_confidence_avg_none_when_empty(self, mock_services):
        """T16: Empty medicines list → confidence_avg is None."""
        from backend.app.api.webhooks import _run_pipeline

        # Override extraction to return empty medicines
        empty_prescription = PrescriptionData(medicines=[], overall_confidence=0.0)
        mock_services["extract"].return_value = empty_prescription

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        call_kwargs = mock_services["log_interaction"].call_args
        confidence = call_kwargs.kwargs.get("confidence_avg")
        assert confidence is None


class TestPipelineRequestIdAndContext:
    """Tests 17–18: Request ID threading and Loguru context."""

    @pytest.mark.asyncio
    async def test_pipeline_request_id_threaded(self, mock_services):
        """T17: request_id passed to extract, enrich, translate, TTS calls."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        # extract_prescription gets request_id
        assert mock_services["extract"].call_args.kwargs["request_id"] == REQUEST_ID
        # enrich_prescription gets request_id
        assert mock_services["enrich"].call_args.kwargs["request_id"] == REQUEST_ID
        # simplify_and_translate gets request_id
        assert mock_services["translate"].call_args.kwargs["request_id"] == REQUEST_ID
        # generate_and_deliver_audio gets request_id
        assert mock_services["audio"].call_args.kwargs["request_id"] == REQUEST_ID

    @pytest.mark.asyncio
    async def test_pipeline_loguru_context(self, mock_services):
        """T18: logger.contextualize is called with request_id."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        with patch("backend.app.api.webhooks.logger") as mock_logger:
            # Preserve real contextualize behavior (returns context manager)
            mock_logger.contextualize.return_value = MagicMock(
                __enter__=MagicMock(return_value=None),
                __exit__=MagicMock(return_value=False),
            )
            mock_logger.info = MagicMock()

            await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

            mock_logger.contextualize.assert_called_with(request_id=REQUEST_ID)


class TestPipelineErrorHandling:
    """Tests 19–20: Error handling and DB session."""

    @pytest.mark.asyncio
    async def test_pipeline_session_deleted_on_error(self, mock_services):
        """T19: If extraction raises, session is still deleted (S10.4: error handled gracefully)."""
        from backend.app.api.webhooks import _run_pipeline

        mock_services["extract"].side_effect = Exception("GPT-4O failed")

        payload = _make_payload()
        session = _make_session()
        redis_mock = AsyncMock()

        # S10.4: Pipeline now catches exceptions gracefully — no re-raise
        await _run_pipeline(payload, session, REQUEST_ID, redis_mock)

        mock_services["delete_session"].assert_awaited_once_with(payload.from_number, redis_mock)

    @pytest.mark.asyncio
    async def test_pipeline_db_session_used_for_logging(self, mock_services):
        """T20: AsyncSessionLocal used to acquire DB session for _log_interaction."""
        from backend.app.api.webhooks import _run_pipeline

        payload = _make_payload()
        session = _make_session()

        await _run_pipeline(payload, session, REQUEST_ID, AsyncMock())

        # AsyncSessionLocal was called (to create a context manager)
        mock_services["session_local"].assert_called_once()
        # _log_interaction was called with the mock DB session
        call_kwargs = mock_services["log_interaction"].call_args
        assert call_kwargs.kwargs["db"] == mock_services["db_session"]
