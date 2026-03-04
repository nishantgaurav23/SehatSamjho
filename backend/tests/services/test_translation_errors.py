"""S7.5 — Tests for translation retry + error handling.

20 tests: exception class (3), retry decorator (5), non-retryable (2),
TranslationError raising (3), retry logging (4), integration (3).
All Claude API calls mocked.
"""

from __future__ import annotations

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest
from loguru import logger

from backend.app.models.schemas import (
    MedicineEntry,
    PrescriptionData,
    TranslationResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_RESPONSE_TEXT = (
    "## Your Prescription Summary\n"
    "\n"
    "### Metformin 500mg\n"
    "Take 500mg twice a day, after meals.\n"
    "\n"
    "**Disclaimer**: This translation is for understanding only. "
    "Please consult your doctor or pharmacist for medical advice."
)


@pytest.fixture()
def sample_prescription() -> PrescriptionData:
    return PrescriptionData(
        doctor_name="Dr. Sharma",
        diagnosis="Type 2 Diabetes",
        medicines=[
            MedicineEntry(
                medicine_name="Metformin",
                dosage="500mg",
                frequency="Twice daily",
                confidence=0.95,
            ),
        ],
        overall_confidence=0.91,
    )


def _make_mock_response(text: str) -> MagicMock:
    """Build a mock anthropic.types.Message with a single TextBlock."""
    block = SimpleNamespace(type="text", text=text)
    response = MagicMock()
    response.content = [block]
    response.usage = SimpleNamespace(input_tokens=100, output_tokens=200)
    return response


def _make_empty_response() -> MagicMock:
    response = MagicMock()
    response.content = []
    response.usage = SimpleNamespace(input_tokens=100, output_tokens=0)
    return response


def _make_whitespace_response() -> MagicMock:
    block = SimpleNamespace(type="text", text="   \n  \t  ")
    response = MagicMock()
    response.content = [block]
    response.usage = SimpleNamespace(input_tokens=100, output_tokens=5)
    return response


def _mock_client_raising(exc: Exception) -> MagicMock:
    """Return a mock client whose messages.create always raises exc."""
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(side_effect=exc)
    return client


def _mock_client_failing_then_succeeding(exc: Exception, success_after: int = 1) -> MagicMock:
    """Return a mock client that fails `success_after` times then succeeds."""
    call_count = 0

    async def _side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= success_after:
            raise exc
        return _make_mock_response(SAMPLE_RESPONSE_TEXT)

    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(side_effect=_side_effect)
    return client


# Patch tenacity wait to avoid real delays in tests
_NO_WAIT_PATCH = patch(
    "backend.app.services.translation.simplify_and_translate.retry.wait",
    return_value=0,
)


# ═══════════════════════════════════════════════════════════════════════════
# Exception Class (3 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestTranslationErrorClass:
    """FR-1: TranslationError exception class."""

    def test_import_translation_error(self):
        from backend.app.services.translation import TranslationError

        assert TranslationError is not None

    def test_translation_error_is_exception(self):
        from backend.app.services.translation import TranslationError

        assert issubclass(TranslationError, Exception)

    def test_translation_error_message(self):
        from backend.app.services.translation import TranslationError

        err = TranslationError("test message")
        assert str(err) == "test message"


# ═══════════════════════════════════════════════════════════════════════════
# Retry Decorator (5 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestRetryDecorator:
    """FR-2: Tenacity retry on transient Anthropic errors."""

    @pytest.mark.asyncio
    async def test_retry_on_api_timeout_error(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        client = _mock_client_failing_then_succeeding(
            anthropic.APITimeoutError(request=MagicMock()), success_after=1
        )
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            _NO_WAIT_PATCH,
        ):
            result = await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-retry-1",
            )
        assert isinstance(result, TranslationResult)
        assert client.messages.create.await_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_api_connection_error(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        client = _mock_client_failing_then_succeeding(
            anthropic.APIConnectionError(request=MagicMock()), success_after=1
        )
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            _NO_WAIT_PATCH,
        ):
            result = await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-retry-2",
            )
        assert isinstance(result, TranslationResult)
        assert client.messages.create.await_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_error(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        resp = MagicMock()
        resp.status_code = 429
        resp.headers = {}
        client = _mock_client_failing_then_succeeding(
            anthropic.RateLimitError(message="rate limited", response=resp, body=None),
            success_after=1,
        )
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            _NO_WAIT_PATCH,
        ):
            result = await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-retry-3",
            )
        assert isinstance(result, TranslationResult)
        assert client.messages.create.await_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_internal_server_error(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        resp = MagicMock()
        resp.status_code = 500
        resp.headers = {}
        client = _mock_client_failing_then_succeeding(
            anthropic.InternalServerError(message="server error", response=resp, body=None),
            success_after=1,
        )
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            _NO_WAIT_PATCH,
        ):
            result = await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-retry-4",
            )
        assert isinstance(result, TranslationResult)
        assert client.messages.create.await_count == 2

    @pytest.mark.asyncio
    async def test_max_3_attempts(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        client = _mock_client_raising(anthropic.APITimeoutError(request=MagicMock()))
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            _NO_WAIT_PATCH,
            pytest.raises(anthropic.APITimeoutError),
        ):
            await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-retry-5",
            )
        assert client.messages.create.await_count == 3


# ═══════════════════════════════════════════════════════════════════════════
# Non-Retryable Errors (2 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestNonRetryableErrors:
    """FR-6: Non-transient errors propagate immediately."""

    @pytest.mark.asyncio
    async def test_no_retry_on_authentication_error(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        resp = MagicMock()
        resp.status_code = 401
        resp.headers = {}
        client = _mock_client_raising(
            anthropic.AuthenticationError(message="invalid key", response=resp, body=None)
        )
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            _NO_WAIT_PATCH,
            pytest.raises(anthropic.AuthenticationError),
        ):
            await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-noretry-1",
            )
        assert client.messages.create.await_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_bad_request_error(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        resp = MagicMock()
        resp.status_code = 400
        resp.headers = {}
        client = _mock_client_raising(
            anthropic.BadRequestError(message="bad request", response=resp, body=None)
        )
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            _NO_WAIT_PATCH,
            pytest.raises(anthropic.BadRequestError),
        ):
            await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-noretry-2",
            )
        assert client.messages.create.await_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# TranslationError Raising (3 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestTranslationErrorRaising:
    """FR-4: TranslationError on empty/malformed response."""

    @pytest.mark.asyncio
    async def test_empty_response_raises_translation_error(self, sample_prescription):
        from backend.app.services.translation import TranslationError, simplify_and_translate

        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(return_value=_make_empty_response())
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            pytest.raises(TranslationError, match="[Ee]mpty"),
        ):
            await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-err-1",
            )

    @pytest.mark.asyncio
    async def test_whitespace_response_raises_translation_error(self, sample_prescription):
        from backend.app.services.translation import TranslationError, simplify_and_translate

        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(return_value=_make_whitespace_response())
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            pytest.raises(TranslationError, match="[Ee]mpty|[Ww]hitespace"),
        ):
            await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-err-2",
            )

    @pytest.mark.asyncio
    async def test_translation_error_includes_request_id(self, sample_prescription):
        from backend.app.services.translation import TranslationError, simplify_and_translate

        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(return_value=_make_empty_response())
        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="DEBUG")
        try:
            with (
                patch("backend.app.services.translation._get_client", return_value=client),
                pytest.raises(TranslationError),
            ):
                await simplify_and_translate(
                    prescription=sample_prescription,
                    language_name="Hindi",
                    language_code="hi",
                    request_id="req-err-3",
                )
            log_output = sink.getvalue()
            assert "req-err-3" in log_output
        finally:
            logger.remove(handler_id)


# ═══════════════════════════════════════════════════════════════════════════
# Retry Logging (4 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestRetryLogging:
    """FR-3/5: Retry logging callback."""

    def test_log_translation_retry_exists(self):
        from backend.app.services.translation import _log_translation_retry

        assert callable(_log_translation_retry)

    def test_retry_callback_logs_attempt(self):
        from backend.app.services.translation import _log_translation_retry

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="DEBUG")
        try:
            state = MagicMock()
            state.attempt_number = 2
            state.next_action = MagicMock()
            state.next_action.sleep = 4.0
            state.outcome = MagicMock()
            state.outcome.exception.return_value = anthropic.APITimeoutError(request=MagicMock())
            _log_translation_retry(state)
            log_output = sink.getvalue()
            assert "2" in log_output
        finally:
            logger.remove(handler_id)

    def test_retry_callback_logs_wait_time(self):
        from backend.app.services.translation import _log_translation_retry

        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="DEBUG")
        try:
            state = MagicMock()
            state.attempt_number = 1
            state.next_action = MagicMock()
            state.next_action.sleep = 2.5
            state.outcome = MagicMock()
            state.outcome.exception.return_value = anthropic.APITimeoutError(request=MagicMock())
            _log_translation_retry(state)
            log_output = sink.getvalue()
            assert "2.5" in log_output
        finally:
            logger.remove(handler_id)

    @pytest.mark.asyncio
    async def test_retry_logs_never_contain_phi(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        client = _mock_client_failing_then_succeeding(
            anthropic.APITimeoutError(request=MagicMock()), success_after=1
        )
        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="DEBUG")
        try:
            with (
                patch("backend.app.services.translation._get_client", return_value=client),
                _NO_WAIT_PATCH,
            ):
                await simplify_and_translate(
                    prescription=sample_prescription,
                    language_name="Hindi",
                    language_code="hi",
                    request_id="req-phi-check",
                )
            log_output = sink.getvalue()
            # Ensure no prescription content leaked into retry logs
            assert "Dr. Sharma" not in log_output
            assert "Type 2 Diabetes" not in log_output
        finally:
            logger.remove(handler_id)


# ═══════════════════════════════════════════════════════════════════════════
# Integration (3 tests)
# ═══════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """End-to-end retry integration."""

    @pytest.mark.asyncio
    async def test_succeeds_after_transient_failure(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        client = _mock_client_failing_then_succeeding(
            anthropic.APITimeoutError(request=MagicMock()), success_after=2
        )
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            _NO_WAIT_PATCH,
        ):
            result = await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-int-1",
            )
        assert isinstance(result, TranslationResult)
        assert client.messages.create.await_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_all_retries_exhausted(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        client = _mock_client_raising(anthropic.APITimeoutError(request=MagicMock()))
        with (
            patch("backend.app.services.translation._get_client", return_value=client),
            _NO_WAIT_PATCH,
            pytest.raises(anthropic.APITimeoutError),
        ):
            await simplify_and_translate(
                prescription=sample_prescription,
                language_name="Hindi",
                language_code="hi",
                request_id="req-int-2",
            )
        assert client.messages.create.await_count == 3

    @pytest.mark.asyncio
    async def test_error_log_includes_language_code(self, sample_prescription):
        from backend.app.services.translation import simplify_and_translate

        client = MagicMock()
        client.messages = MagicMock()
        client.messages.create = AsyncMock(return_value=_make_empty_response())
        sink = io.StringIO()
        handler_id = logger.add(sink, format="{message}", level="DEBUG")
        try:
            with patch("backend.app.services.translation._get_client", return_value=client):
                try:
                    await simplify_and_translate(
                        prescription=sample_prescription,
                        language_name="Tamil",
                        language_code="ta",
                        request_id="req-int-3",
                    )
                except Exception:
                    pass
            log_output = sink.getvalue()
            assert "ta" in log_output
        finally:
            logger.remove(handler_id)
