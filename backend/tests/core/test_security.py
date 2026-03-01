"""Tests for S1.5 — Twilio HMAC Verification (backend/app/core/security.py)."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.app.core.security import validate_twilio_signature


def _make_mock_request(
    url: str = "https://example.com/webhook/whatsapp",
    headers: dict | None = None,
    form_data: dict | None = None,
):
    """Build a mock FastAPI Request with configurable URL, headers, and form body."""
    request = AsyncMock()
    request.url = MagicMock()
    request.url.__str__ = lambda self: url
    request.url.scheme = url.split("://")[0]
    request.url.hostname = url.split("://")[1].split("/")[0].split(":")[0]
    path = "/" + "/".join(url.split("://")[1].split("/")[1:])
    request.url.path = path
    request.url.port = None

    _headers = headers or {}
    request.headers = _headers

    async def _form():
        return form_data or {}

    request.form = _form
    return request


# ────────────────────────────────────────────────────────────────────────────
# Test 1: valid signature passes
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_valid_signature_passes():
    """A request with a valid HMAC signature should pass without exception."""
    request = _make_mock_request(
        headers={"X-Twilio-Signature": "valid-sig-abc123"},
    )
    with patch("backend.app.core.security._get_request_validator") as mock_get_validator:
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        mock_get_validator.return_value = mock_validator

        result = await validate_twilio_signature(request)
        assert result is None  # pass-through dependency


# ────────────────────────────────────────────────────────────────────────────
# Test 2: invalid signature returns 403
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_invalid_signature_returns_403():
    """A request with a wrong/tampered signature should raise HTTP 403."""
    request = _make_mock_request(
        headers={"X-Twilio-Signature": "bad-sig"},
    )
    with patch("backend.app.core.security._get_request_validator") as mock_get_validator:
        mock_validator = MagicMock()
        mock_validator.validate.return_value = False
        mock_get_validator.return_value = mock_validator

        with pytest.raises(HTTPException) as exc_info:
            await validate_twilio_signature(request)
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Invalid Twilio signature"


# ────────────────────────────────────────────────────────────────────────────
# Test 3: missing signature header returns 403
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_missing_signature_header_returns_403():
    """A request with no X-Twilio-Signature header should raise HTTP 403."""
    request = _make_mock_request(headers={})

    with pytest.raises(HTTPException) as exc_info:
        await validate_twilio_signature(request)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Invalid Twilio signature"


# ────────────────────────────────────────────────────────────────────────────
# Test 4: empty signature returns 403
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_empty_signature_returns_403():
    """A request with an empty X-Twilio-Signature should raise HTTP 403."""
    request = _make_mock_request(headers={"X-Twilio-Signature": ""})

    with pytest.raises(HTTPException) as exc_info:
        await validate_twilio_signature(request)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Invalid Twilio signature"


# ────────────────────────────────────────────────────────────────────────────
# Test 5: uses TWILIO_AUTH_TOKEN from settings
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_uses_twilio_auth_token_from_settings():
    """The RequestValidator must be initialised with settings.TWILIO_AUTH_TOKEN."""
    with (
        patch("backend.app.core.security.RequestValidator") as mock_rv_class,
        patch("backend.app.core.security.settings") as mock_settings,
    ):
        mock_settings.TWILIO_AUTH_TOKEN = "my-secret-token"
        mock_rv_class.return_value = MagicMock()

        # Force re-creation by importing the factory
        from backend.app.core.security import _get_request_validator

        # Clear any cached validator
        with patch.dict("backend.app.core.security.__dict__", {"_validator": None}):
            _get_request_validator()
            mock_rv_class.assert_called_once_with("my-secret-token")


# ────────────────────────────────────────────────────────────────────────────
# Test 6: form body included in validation
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_form_body_included_in_validation():
    """POST form parameters must be passed to RequestValidator.validate()."""
    form_data = {"Body": "Hello", "From": "whatsapp:+919999999999"}
    request = _make_mock_request(
        headers={"X-Twilio-Signature": "some-sig"},
        form_data=form_data,
    )
    with patch("backend.app.core.security._get_request_validator") as mock_get_validator:
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        mock_get_validator.return_value = mock_validator

        await validate_twilio_signature(request)

        # Verify form params were passed to validate()
        # validate() is called as validate(url, params, signature) — positional
        call_args = mock_validator.validate.call_args
        assert call_args[0][1] == form_data


# ────────────────────────────────────────────────────────────────────────────
# Test 7: URL reconstruction — direct (no proxy)
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_url_reconstruction_direct():
    """Without proxy headers, the URL should match request.url as-is."""
    url = "https://myapp.example.com/webhook/whatsapp"
    request = _make_mock_request(
        url=url,
        headers={"X-Twilio-Signature": "sig"},
    )
    with patch("backend.app.core.security._get_request_validator") as mock_get_validator:
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        mock_get_validator.return_value = mock_validator

        await validate_twilio_signature(request)

        call_args = mock_validator.validate.call_args
        validated_url = call_args[0][0] if call_args[0] else call_args[1].get("uri")
        assert validated_url == url


# ────────────────────────────────────────────────────────────────────────────
# Test 8: URL reconstruction — behind proxy
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_url_reconstruction_behind_proxy():
    """With X-Forwarded-Proto and X-Forwarded-Host, reconstruct the external URL."""
    internal_url = "http://127.0.0.1:8000/webhook/whatsapp"
    request = _make_mock_request(
        url=internal_url,
        headers={
            "X-Twilio-Signature": "sig",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "public.example.com",
        },
    )
    with patch("backend.app.core.security._get_request_validator") as mock_get_validator:
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        mock_get_validator.return_value = mock_validator

        await validate_twilio_signature(request)

        call_args = mock_validator.validate.call_args
        validated_url = call_args[0][0] if call_args[0] else call_args[1].get("uri")
        assert validated_url == "https://public.example.com/webhook/whatsapp"


# ────────────────────────────────────────────────────────────────────────────
# Test 9: dependency is async
# ────────────────────────────────────────────────────────────────────────────
def test_dependency_is_async():
    """validate_twilio_signature must be an async function for FastAPI Depends()."""
    assert inspect.iscoroutinefunction(validate_twilio_signature)


# ────────────────────────────────────────────────────────────────────────────
# Test 10: valid signature with empty body
# ────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_valid_signature_with_empty_body():
    """POST with no form fields but a valid signature should pass."""
    request = _make_mock_request(
        headers={"X-Twilio-Signature": "valid-sig"},
        form_data={},
    )
    with patch("backend.app.core.security._get_request_validator") as mock_get_validator:
        mock_validator = MagicMock()
        mock_validator.validate.return_value = True
        mock_get_validator.return_value = mock_validator

        result = await validate_twilio_signature(request)
        assert result is None

        # Verify empty dict was passed as params
        # validate() is called as validate(url, params, signature) — positional
        call_args = mock_validator.validate.call_args
        assert call_args[0][1] == {}
