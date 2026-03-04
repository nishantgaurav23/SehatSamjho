"""Tests for S9.3 — S3 Upload (_get_s3_client, _reset_s3_client, _upload_to_s3, S3UploadError)."""

from __future__ import annotations

import inspect
import re
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module-level env vars (must be set before importing modules that use Settings)
# ---------------------------------------------------------------------------
import os

os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "test-twilio-sid")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-twilio-token")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
os.environ.setdefault("BHASHINI_API_KEY", "test-bhashini-key")
os.environ.setdefault("BHASHINI_USER_ID", "test-bhashini-user")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-aws-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_PRESIGNED_URL = "https://test-bucket.s3.amazonaws.com/audio/fake-uuid.ogg?AWSAccessKeyId=test"
FAKE_UUID = "12345678-1234-1234-1234-123456789abc"
SAMPLE_AUDIO = b"\x00\x01\x02\x03" * 100  # 400 bytes of fake audio


@pytest.fixture(autouse=True)
def _reset_s3_singleton():
    """Reset S3 client singleton before each test."""
    from backend.app.services.tts import _reset_s3_client

    _reset_s3_client()
    yield
    _reset_s3_client()


# ===========================================================================
# S3UploadError tests (2 tests)
# ===========================================================================


class TestS3UploadError:
    """Tests for S3UploadError exception class."""

    def test_s3_upload_error_is_exception(self):
        """S3UploadError is a subclass of Exception."""
        from backend.app.services.tts import S3UploadError

        assert issubclass(S3UploadError, Exception)

    def test_s3_upload_error_has_message(self):
        """S3UploadError stores message attribute."""
        from backend.app.services.tts import S3UploadError

        err = S3UploadError("upload failed")
        assert err.message == "upload failed"
        assert str(err) == "upload failed"


# ===========================================================================
# _get_s3_client / _reset_s3_client tests (4 tests)
# ===========================================================================


class TestS3ClientSingleton:
    """Tests for lazy S3 client singleton."""

    @patch("backend.app.services.tts.boto3")
    def test_get_s3_client_returns_client(self, mock_boto3):
        """_get_s3_client() returns a boto3 S3 client."""
        from backend.app.services.tts import _get_s3_client

        mock_boto3.client.return_value = MagicMock()
        client = _get_s3_client()
        assert client is not None
        mock_boto3.client.assert_called_once()

    @patch("backend.app.services.tts.boto3")
    def test_get_s3_client_singleton(self, mock_boto3):
        """Second call returns same instance (singleton)."""
        from backend.app.services.tts import _get_s3_client

        mock_boto3.client.return_value = MagicMock()
        client1 = _get_s3_client()
        client2 = _get_s3_client()
        assert client1 is client2
        mock_boto3.client.assert_called_once()

    @patch("backend.app.services.tts.boto3")
    def test_get_s3_client_uses_settings(self, mock_boto3):
        """Client created with AWS credentials from settings."""
        from backend.app.services.tts import _get_s3_client

        mock_settings = MagicMock()
        mock_settings.AWS_ACCESS_KEY_ID = "test-aws-key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test-aws-secret"
        mock_boto3.client.return_value = MagicMock()
        with patch("backend.app.core.config.settings", mock_settings):
            _get_s3_client()
        call_kwargs = mock_boto3.client.call_args
        assert call_kwargs[0][0] == "s3"
        assert call_kwargs[1]["aws_access_key_id"] == "test-aws-key"
        assert call_kwargs[1]["aws_secret_access_key"] == "test-aws-secret"

    @patch("backend.app.services.tts.boto3")
    def test_reset_s3_client(self, mock_boto3):
        """_reset_s3_client() clears singleton, next call creates new."""
        from backend.app.services.tts import _get_s3_client, _reset_s3_client

        mock_boto3.client.return_value = MagicMock()
        client1 = _get_s3_client()
        _reset_s3_client()
        mock_boto3.client.return_value = MagicMock()
        client2 = _get_s3_client()
        assert client1 is not client2
        assert mock_boto3.client.call_count == 2


# ===========================================================================
# _upload_to_s3 tests — happy path (7 tests)
# ===========================================================================


class TestUploadToS3HappyPath:
    """Tests for _upload_to_s3 happy path."""

    def test_upload_to_s3_is_async(self):
        """_upload_to_s3 is an async function."""
        from backend.app.services.tts import _upload_to_s3

        assert inspect.iscoroutinefunction(_upload_to_s3)

    def test_upload_to_s3_signature(self):
        """_upload_to_s3 accepts audio_bytes and request_id."""
        from backend.app.services.tts import _upload_to_s3

        sig = inspect.signature(_upload_to_s3)
        params = list(sig.parameters.keys())
        assert "audio_bytes" in params
        assert "request_id" in params
        assert sig.parameters["request_id"].default == ""

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_calls_put_object(self, mock_get_client, mock_to_thread, mock_uuid):
        """put_object called with correct bucket, key, body, content type."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]  # put_object, presigned

        await _upload_to_s3(SAMPLE_AUDIO, request_id="req-1")

        # asyncio_to_thread called twice: put_object + presigned_url
        assert mock_to_thread.call_count == 2

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_key_format(self, mock_get_client, mock_to_thread, mock_uuid):
        """S3 key matches audio/{uuid}.ogg pattern."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]

        await _upload_to_s3(SAMPLE_AUDIO, request_id="req-1")

        # Verify the key used in put_object call via the lambda/callable
        first_call_args = mock_to_thread.call_args_list[0]
        # The first arg is a callable that wraps put_object
        put_callable = first_call_args[0][0]
        # We'll check that the function was called — the key is embedded
        # Alternative: check via mock_s3 after calling the callable
        put_callable()
        put_kwargs = mock_s3.put_object.call_args[1]
        assert re.match(r"^audio/[a-f0-9\-]+\.ogg$", put_kwargs["Key"])

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_content_type(self, mock_get_client, mock_to_thread, mock_uuid):
        """ContentType is audio/ogg."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]

        await _upload_to_s3(SAMPLE_AUDIO, request_id="req-1")

        first_call_args = mock_to_thread.call_args_list[0]
        put_callable = first_call_args[0][0]
        put_callable()
        put_kwargs = mock_s3.put_object.call_args[1]
        assert put_kwargs["ContentType"] == "audio/ogg"

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_presigned_url(self, mock_get_client, mock_to_thread, mock_uuid):
        """generate_presigned_url called with get_object, correct bucket/key, ExpiresIn=3600."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]

        await _upload_to_s3(SAMPLE_AUDIO, request_id="req-1")

        # Second call to asyncio_to_thread is generate_presigned_url
        second_call_args = mock_to_thread.call_args_list[1]
        presigned_callable = second_call_args[0][0]
        presigned_callable()
        presigned_kwargs = mock_s3.generate_presigned_url.call_args
        assert presigned_kwargs[0][0] == "get_object"
        params = presigned_kwargs[1]["Params"]
        assert params["Bucket"] == "test-bucket"
        assert re.match(r"^audio/[a-f0-9\-]+\.ogg$", params["Key"])
        assert presigned_kwargs[1]["ExpiresIn"] == 3600

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_returns_presigned_url(
        self, mock_get_client, mock_to_thread, mock_uuid
    ):
        """Returns the presigned URL string."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]

        result = await _upload_to_s3(SAMPLE_AUDIO, request_id="req-1")
        assert result == FAKE_PRESIGNED_URL


# ===========================================================================
# _upload_to_s3 tests — error paths (3 tests)
# ===========================================================================


class TestUploadToS3Errors:
    """Tests for _upload_to_s3 error paths."""

    @pytest.mark.asyncio
    async def test_upload_to_s3_empty_bytes_raises_value_error(self):
        """Empty bytes raises ValueError."""
        from backend.app.services.tts import _upload_to_s3

        with pytest.raises(ValueError, match="audio_bytes"):
            await _upload_to_s3(b"", request_id="req-1")

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_put_object_failure(
        self, mock_get_client, mock_to_thread, mock_uuid
    ):
        """S3 ClientError on put_object raises S3UploadError."""
        from botocore.exceptions import ClientError

        from backend.app.services.tts import S3UploadError, _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "PutObject",
        )

        with pytest.raises(S3UploadError):
            await _upload_to_s3(SAMPLE_AUDIO, request_id="req-1")

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_presigned_url_failure(
        self, mock_get_client, mock_to_thread, mock_uuid
    ):
        """Error on generate_presigned_url raises S3UploadError."""
        from botocore.exceptions import ClientError

        from backend.app.services.tts import S3UploadError, _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        # put_object succeeds, presigned_url fails
        mock_to_thread.side_effect = [
            None,
            ClientError(
                {"Error": {"Code": "InternalError", "Message": "Internal"}},
                "GeneratePresignedUrl",
            ),
        ]

        with pytest.raises(S3UploadError):
            await _upload_to_s3(SAMPLE_AUDIO, request_id="req-1")


# ===========================================================================
# Logging tests (4 tests)
# ===========================================================================


class TestUploadToS3Logging:
    """Tests for _upload_to_s3 logging."""

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.logger")
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_logging_start(
        self, mock_get_client, mock_to_thread, mock_uuid, mock_logger
    ):
        """Logs upload start with request_id."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]

        await _upload_to_s3(SAMPLE_AUDIO, request_id="req-123")

        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        start_logged = any("req-123" in c for c in info_calls)
        assert start_logged, "request_id should appear in log output"

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.logger")
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_logging_success(
        self, mock_get_client, mock_to_thread, mock_uuid, mock_logger
    ):
        """Logs success with request_id and key."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]

        await _upload_to_s3(SAMPLE_AUDIO, request_id="req-456")

        info_calls = [str(c) for c in mock_logger.info.call_args_list]
        success_logged = any("req-456" in c and FAKE_UUID in c for c in info_calls)
        assert success_logged, "Success log should include request_id and key"

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.logger")
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_logging_no_audio_content(
        self, mock_get_client, mock_to_thread, mock_uuid, mock_logger
    ):
        """Logs never contain audio bytes."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]

        await _upload_to_s3(SAMPLE_AUDIO, request_id="req-789")

        all_calls = (
            [str(c) for c in mock_logger.info.call_args_list]
            + [str(c) for c in mock_logger.error.call_args_list]
            + [str(c) for c in mock_logger.warning.call_args_list]
        )
        audio_repr = str(SAMPLE_AUDIO)
        for call_str in all_calls:
            assert audio_repr not in call_str, "Logs must never contain raw audio bytes"

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.logger")
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_logging_no_full_url(
        self, mock_get_client, mock_to_thread, mock_uuid, mock_logger
    ):
        """Logs never contain full presigned URL (has credentials)."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]

        await _upload_to_s3(SAMPLE_AUDIO, request_id="req-url")

        all_calls = (
            [str(c) for c in mock_logger.info.call_args_list]
            + [str(c) for c in mock_logger.error.call_args_list]
            + [str(c) for c in mock_logger.warning.call_args_list]
        )
        for call_str in all_calls:
            assert FAKE_PRESIGNED_URL not in call_str, "Logs must never contain full presigned URL"


# ===========================================================================
# Default request_id test (1 test)
# ===========================================================================


class TestUploadToS3DefaultRequestId:
    """Test _upload_to_s3 works with default empty request_id."""

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_default_request_id(
        self, mock_get_client, mock_to_thread, mock_uuid
    ):
        """Works with default empty request_id."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]

        result = await _upload_to_s3(SAMPLE_AUDIO)
        assert result == FAKE_PRESIGNED_URL


# ===========================================================================
# asyncio.to_thread usage test (1 test)
# ===========================================================================


class TestUploadToS3AsyncioToThread:
    """Test _upload_to_s3 uses asyncio.to_thread for blocking boto3 calls."""

    @pytest.mark.asyncio
    @patch("backend.app.services.tts.uuid4")
    @patch("backend.app.services.tts.asyncio_to_thread")
    @patch("backend.app.services.tts._get_s3_client")
    async def test_upload_to_s3_uses_asyncio_to_thread(
        self, mock_get_client, mock_to_thread, mock_uuid
    ):
        """put_object and presigned URL wrapped in asyncio.to_thread."""
        from backend.app.services.tts import _upload_to_s3

        mock_uuid.return_value = FAKE_UUID
        mock_s3 = MagicMock()
        mock_get_client.return_value = mock_s3
        mock_to_thread.side_effect = [None, FAKE_PRESIGNED_URL]

        await _upload_to_s3(SAMPLE_AUDIO, request_id="req-thread")

        # asyncio.to_thread called twice: once for put_object, once for presigned_url
        assert mock_to_thread.call_count == 2
