"""S10.4 — Pipeline Error Handler tests.

20 tests covering:
- 5 error message constants
- 3 function signature tests (_handle_pipeline_error)
- 5 exception→message mapping tests
- 1 subclass priority test
- 4 pipeline integration tests (send, log, cleanup, send-failure)
- 1 PHI-safety test
- 1 error_code classname test
"""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1–5: Error message constants
# ---------------------------------------------------------------------------


class TestErrorMessageConstants:
    """Verify all 5 error message constants exist and are non-empty strings."""

    def test_not_medical_doc_message_constant(self):
        from backend.app.api.webhooks import NOT_MEDICAL_DOC_MESSAGE

        assert isinstance(NOT_MEDICAL_DOC_MESSAGE, str)
        assert len(NOT_MEDICAL_DOC_MESSAGE) > 0

    def test_image_not_readable_message_constant(self):
        from backend.app.api.webhooks import IMAGE_NOT_READABLE_MESSAGE

        assert isinstance(IMAGE_NOT_READABLE_MESSAGE, str)
        assert len(IMAGE_NOT_READABLE_MESSAGE) > 0

    def test_translation_error_message_constant(self):
        from backend.app.api.webhooks import TRANSLATION_ERROR_MESSAGE

        assert isinstance(TRANSLATION_ERROR_MESSAGE, str)
        assert len(TRANSLATION_ERROR_MESSAGE) > 0

    def test_extraction_error_message_constant(self):
        from backend.app.api.webhooks import EXTRACTION_ERROR_MESSAGE

        assert isinstance(EXTRACTION_ERROR_MESSAGE, str)
        assert len(EXTRACTION_ERROR_MESSAGE) > 0

    def test_generic_pipeline_error_message_constant(self):
        from backend.app.api.webhooks import GENERIC_PIPELINE_ERROR_MESSAGE

        assert isinstance(GENERIC_PIPELINE_ERROR_MESSAGE, str)
        assert len(GENERIC_PIPELINE_ERROR_MESSAGE) > 0


# ---------------------------------------------------------------------------
# 6–8: Function signature tests
# ---------------------------------------------------------------------------


class TestHandlePipelineErrorSignature:
    """Verify _handle_pipeline_error is importable, correct signature, sync."""

    def test_handle_pipeline_error_importable(self):
        from backend.app.api.webhooks import _handle_pipeline_error

        assert callable(_handle_pipeline_error)

    def test_handle_pipeline_error_signature(self):
        from backend.app.api.webhooks import _handle_pipeline_error

        sig = inspect.signature(_handle_pipeline_error)
        params = list(sig.parameters.keys())
        assert "exc" in params
        # Returns str
        result = _handle_pipeline_error(Exception("test"))
        assert isinstance(result, str)

    def test_handle_pipeline_error_is_sync(self):
        from backend.app.api.webhooks import _handle_pipeline_error

        assert not asyncio.iscoroutinefunction(_handle_pipeline_error)


# ---------------------------------------------------------------------------
# 9–13: Exception→message mapping tests
# ---------------------------------------------------------------------------


class TestExceptionMapping:
    """Verify each exception type maps to the correct patient-friendly message."""

    def test_maps_not_medical_document_error(self):
        from backend.app.api.webhooks import (
            NOT_MEDICAL_DOC_MESSAGE,
            _handle_pipeline_error,
        )
        from backend.app.services.extraction import NotMedicalDocumentError

        result = _handle_pipeline_error(NotMedicalDocumentError("test"))
        assert result == NOT_MEDICAL_DOC_MESSAGE

    def test_maps_image_not_readable_error(self):
        from backend.app.api.webhooks import (
            IMAGE_NOT_READABLE_MESSAGE,
            _handle_pipeline_error,
        )
        from backend.app.services.extraction import ImageNotReadableError

        result = _handle_pipeline_error(ImageNotReadableError("test"))
        assert result == IMAGE_NOT_READABLE_MESSAGE

    def test_maps_translation_error(self):
        from backend.app.api.webhooks import (
            TRANSLATION_ERROR_MESSAGE,
            _handle_pipeline_error,
        )
        from backend.app.services.translation import TranslationError

        result = _handle_pipeline_error(TranslationError("test"))
        assert result == TRANSLATION_ERROR_MESSAGE

    def test_maps_extraction_error_base(self):
        from backend.app.api.webhooks import (
            EXTRACTION_ERROR_MESSAGE,
            _handle_pipeline_error,
        )
        from backend.app.services.extraction import ExtractionError

        result = _handle_pipeline_error(ExtractionError("test"))
        assert result == EXTRACTION_ERROR_MESSAGE

    def test_maps_generic_exception(self):
        from backend.app.api.webhooks import (
            GENERIC_PIPELINE_ERROR_MESSAGE,
            _handle_pipeline_error,
        )

        for exc_cls in (ValueError, RuntimeError, TypeError, KeyError):
            result = _handle_pipeline_error(exc_cls("test"))
            assert result == GENERIC_PIPELINE_ERROR_MESSAGE


# ---------------------------------------------------------------------------
# 14: Subclass priority test
# ---------------------------------------------------------------------------


class TestSubclassPriority:
    """Subclasses of specific errors should match their parent's specific message."""

    def test_subclass_priority(self):
        from backend.app.api.webhooks import (
            NOT_MEDICAL_DOC_MESSAGE,
            _handle_pipeline_error,
        )
        from backend.app.services.extraction import NotMedicalDocumentError

        class CustomNotMedical(NotMedicalDocumentError):
            pass

        result = _handle_pipeline_error(CustomNotMedical("test"))
        assert result == NOT_MEDICAL_DOC_MESSAGE


# ---------------------------------------------------------------------------
# 15–18: Pipeline integration tests
# ---------------------------------------------------------------------------


class TestPipelineErrorIntegration:
    """Integration tests: error→send→log→cleanup in _run_pipeline()."""

    @pytest.fixture
    def mock_payload(self):
        from backend.app.models.schemas import WebhookPayload

        return WebhookPayload(
            from_number="+15551234567",
            body="",
            num_media=1,
            media_url="https://example.com/image.jpg",
            media_content_type="image/jpeg",
        )

    @pytest.fixture
    def mock_session(self):
        from backend.app.models.schemas import SessionState, SessionStatus

        return SessionState(
            status=SessionStatus.PROCESSING,
            language_code="hi",
            language_name="Hindi",
            request_id="test-req-id",
            created_at="2026-01-01T00:00:00Z",
        )

    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_pipeline_error_sends_message(self, mock_payload, mock_session, mock_redis):
        """When pipeline raises NotMedicalDocumentError, user receives tailored message."""
        from backend.app.api.webhooks import (
            NOT_MEDICAL_DOC_MESSAGE,
            _run_pipeline,
        )
        from backend.app.services.extraction import NotMedicalDocumentError

        mock_db = AsyncMock()
        mock_db_ctx = MagicMock()
        mock_db_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "backend.app.api.webhooks._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image-bytes",
            ),
            patch(
                "backend.app.api.webhooks.store_prescription_image",
                new_callable=AsyncMock,
                return_value="prescriptions/test/img.jpg",
            ),
            patch(
                "backend.app.api.webhooks.extract_prescription_from_bytes",
                new_callable=AsyncMock,
                side_effect=NotMedicalDocumentError("not medical"),
            ),
            patch(
                "backend.app.api.webhooks.send_text_message",
                new_callable=AsyncMock,
            ) as mock_send,
            patch(
                "backend.app.api.webhooks.AsyncSessionLocal",
                return_value=mock_db_ctx,
            ),
        ):
            await _run_pipeline(mock_payload, mock_session, "req-123", mock_redis)

        # Verify the error message was sent to the user
        mock_send.assert_called_once_with(mock_payload.from_number, NOT_MEDICAL_DOC_MESSAGE)

    @pytest.mark.asyncio
    async def test_pipeline_error_logs_interaction(self, mock_payload, mock_session, mock_redis):
        """When pipeline raises error, interaction logged with status=ERROR and error_code."""
        from backend.app.api.webhooks import _run_pipeline
        from backend.app.db.models import InteractionStatus
        from backend.app.services.extraction import ImageNotReadableError

        mock_db = AsyncMock()
        mock_db_ctx = MagicMock()
        mock_db_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "backend.app.api.webhooks._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image-bytes",
            ),
            patch(
                "backend.app.api.webhooks.store_prescription_image",
                new_callable=AsyncMock,
                return_value="prescriptions/test/img.jpg",
            ),
            patch(
                "backend.app.api.webhooks.extract_prescription_from_bytes",
                new_callable=AsyncMock,
                side_effect=ImageNotReadableError("blurry"),
            ),
            patch(
                "backend.app.api.webhooks.send_text_message",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.app.api.webhooks.AsyncSessionLocal",
                return_value=mock_db_ctx,
            ),
            patch(
                "backend.app.api.webhooks._log_interaction",
                new_callable=AsyncMock,
            ) as mock_log,
        ):
            await _run_pipeline(mock_payload, mock_session, "req-456", mock_redis)

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args
        # Check positional or keyword args for status and error_code
        kwargs = call_kwargs.kwargs if call_kwargs.kwargs else {}
        if not kwargs:
            kwargs = dict(
                zip(
                    [
                        "phone_number",
                        "language_code",
                        "status",
                        "request_id",
                        "db",
                    ],
                    call_kwargs.args,
                )
            )
            kwargs.update(call_kwargs.kwargs)

        assert kwargs.get("status") == InteractionStatus.ERROR
        assert kwargs.get("error_code") == "ImageNotReadableError"

    @pytest.mark.asyncio
    async def test_pipeline_error_session_cleanup(self, mock_payload, mock_session, mock_redis):
        """When pipeline raises error, session is still deleted from Redis."""
        from backend.app.api.webhooks import _run_pipeline
        from backend.app.services.extraction import ExtractionError

        mock_db = AsyncMock()
        mock_db_ctx = MagicMock()
        mock_db_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "backend.app.api.webhooks._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image-bytes",
            ),
            patch(
                "backend.app.api.webhooks.store_prescription_image",
                new_callable=AsyncMock,
                return_value="prescriptions/test/img.jpg",
            ),
            patch(
                "backend.app.api.webhooks.extract_prescription_from_bytes",
                new_callable=AsyncMock,
                side_effect=ExtractionError("fail"),
            ),
            patch(
                "backend.app.api.webhooks.send_text_message",
                new_callable=AsyncMock,
            ),
            patch(
                "backend.app.api.webhooks.AsyncSessionLocal",
                return_value=mock_db_ctx,
            ),
            patch(
                "backend.app.api.webhooks._log_interaction",
                new_callable=AsyncMock,
            ),
        ):
            await _run_pipeline(mock_payload, mock_session, "req-789", mock_redis)

        # Verify session was deleted
        mock_redis.delete.assert_called_once()
        call_args = mock_redis.delete.call_args[0][0]
        assert mock_payload.from_number in call_args

    @pytest.mark.asyncio
    async def test_pipeline_error_send_failure_handled(
        self, mock_payload, mock_session, mock_redis
    ):
        """If sending the error message itself fails, no crash, failure is logged."""
        from backend.app.api.webhooks import _run_pipeline
        from backend.app.services.extraction import NotMedicalDocumentError

        mock_db = AsyncMock()
        mock_db_ctx = MagicMock()
        mock_db_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch(
                "backend.app.api.webhooks._download_image",
                new_callable=AsyncMock,
                return_value=b"fake-image-bytes",
            ),
            patch(
                "backend.app.api.webhooks.store_prescription_image",
                new_callable=AsyncMock,
                return_value="prescriptions/test/img.jpg",
            ),
            patch(
                "backend.app.api.webhooks.extract_prescription_from_bytes",
                new_callable=AsyncMock,
                side_effect=NotMedicalDocumentError("not medical"),
            ),
            patch(
                "backend.app.api.webhooks.send_text_message",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Twilio down"),
            ),
            patch(
                "backend.app.api.webhooks.AsyncSessionLocal",
                return_value=mock_db_ctx,
            ),
            patch(
                "backend.app.api.webhooks._log_interaction",
                new_callable=AsyncMock,
            ),
        ):
            # Should NOT raise — gracefully handles send failure
            await _run_pipeline(mock_payload, mock_session, "req-err", mock_redis)

        # Session should still be cleaned up
        mock_redis.delete.assert_called_once()


# ---------------------------------------------------------------------------
# 19: PHI-safety test
# ---------------------------------------------------------------------------


class TestPHISafety:
    """Error message constants must not contain any PHI placeholders."""

    def test_error_messages_no_phi(self):
        from backend.app.api.webhooks import (
            EXTRACTION_ERROR_MESSAGE,
            GENERIC_PIPELINE_ERROR_MESSAGE,
            IMAGE_NOT_READABLE_MESSAGE,
            NOT_MEDICAL_DOC_MESSAGE,
            TRANSLATION_ERROR_MESSAGE,
        )

        phi_patterns = [
            "{phone}",
            "{name}",
            "{image}",
            "{url}",
            "{patient}",
            "{doctor}",
            "phone_number",
            "image_url",
        ]
        for msg in (
            NOT_MEDICAL_DOC_MESSAGE,
            IMAGE_NOT_READABLE_MESSAGE,
            TRANSLATION_ERROR_MESSAGE,
            EXTRACTION_ERROR_MESSAGE,
            GENERIC_PIPELINE_ERROR_MESSAGE,
        ):
            for pattern in phi_patterns:
                assert pattern not in msg.lower(), f"PHI pattern '{pattern}' found in error message"


# ---------------------------------------------------------------------------
# 20: Error code from exception classname
# ---------------------------------------------------------------------------


class TestErrorCodeFromClassname:
    """error_code should be type(exc).__name__ for various exception types."""

    @pytest.mark.asyncio
    async def test_error_code_from_exception_classname(self):
        """Various exception types produce their class name as error_code."""
        from backend.app.api.webhooks import _run_pipeline
        from backend.app.models.schemas import (
            SessionState,
            SessionStatus,
            WebhookPayload,
        )
        from backend.app.services.extraction import ExtractionError
        from backend.app.services.translation import TranslationError

        payload = WebhookPayload(
            from_number="+15559999999",
            body="",
            num_media=1,
            media_url="https://example.com/img.jpg",
            media_content_type="image/jpeg",
        )
        session = SessionState(
            status=SessionStatus.PROCESSING,
            language_code="hi",
            language_name="Hindi",
            request_id="test-req",
            created_at="2026-01-01T00:00:00Z",
        )
        mock_redis = AsyncMock()

        for exc_cls, expected_name in [
            (ExtractionError, "ExtractionError"),
            (TranslationError, "TranslationError"),
            (ValueError, "ValueError"),
        ]:
            mock_db = AsyncMock()
            mock_db_ctx = MagicMock()
            mock_db_ctx.__aenter__ = AsyncMock(return_value=mock_db)
            mock_db_ctx.__aexit__ = AsyncMock(return_value=False)

            with (
                patch(
                    "backend.app.api.webhooks._download_image",
                    new_callable=AsyncMock,
                    return_value=b"fake-image-bytes",
                ),
                patch(
                    "backend.app.api.webhooks.store_prescription_image",
                    new_callable=AsyncMock,
                    return_value="prescriptions/test/img.jpg",
                ),
                patch(
                    "backend.app.api.webhooks.extract_prescription_from_bytes",
                    new_callable=AsyncMock,
                    side_effect=exc_cls("test"),
                ),
                patch(
                    "backend.app.api.webhooks.send_text_message",
                    new_callable=AsyncMock,
                ),
                patch(
                    "backend.app.api.webhooks.AsyncSessionLocal",
                    return_value=mock_db_ctx,
                ),
                patch(
                    "backend.app.api.webhooks._log_interaction",
                    new_callable=AsyncMock,
                ) as mock_log,
            ):
                await _run_pipeline(payload, session, f"req-{expected_name}", mock_redis)

            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs.get("error_code") == expected_name, (
                f"Expected error_code={expected_name}, got {call_kwargs.get('error_code')}"
            )
