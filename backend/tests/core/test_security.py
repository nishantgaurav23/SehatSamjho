"""Tests for app/core/security.py

Tests:
    - hash_phone returns a 64-char hex string
    - hash_phone is deterministic
    - hash_phone differs for different inputs
    - hash_phone includes the whatsapp: prefix in the hash
    - verify_twilio_signature returns True when validation disabled (dev mode)
    - verify_twilio_signature returns False for bad signature (prod mode)
    - verify_twilio_signature returns True for correct signature (prod mode)
"""

import hashlib
from unittest.mock import patch

import pytest

from app.core.security import hash_phone, verify_twilio_signature


# ── hash_phone ─────────────────────────────────────────────────────────────────

def test_hash_phone_returns_64_char_hex():
    result = hash_phone("whatsapp:+919876543210")
    assert len(result) == 64
    assert all(c in "0123456789abcdef" for c in result)


def test_hash_phone_is_deterministic():
    phone = "whatsapp:+919876543210"
    assert hash_phone(phone) == hash_phone(phone)


def test_hash_phone_differs_for_different_inputs():
    assert hash_phone("whatsapp:+919876543210") != hash_phone("whatsapp:+919876543211")


def test_hash_phone_includes_prefix():
    """'whatsapp:+91...' and '+91...' must produce different hashes."""
    assert hash_phone("whatsapp:+919876543210") != hash_phone("+919876543210")


def test_hash_phone_matches_manual_sha256():
    phone = "whatsapp:+919876543210"
    expected = hashlib.sha256(phone.encode()).hexdigest()
    assert hash_phone(phone) == expected


# ── verify_twilio_signature ────────────────────────────────────────────────────

def test_verify_returns_true_when_validation_disabled():
    """In development (validate_twilio_signature=False) always returns True."""
    with patch("app.core.security.settings") as mock_settings:
        mock_settings.validate_twilio_signature = False
        result = verify_twilio_signature(
            url="https://example.com/webhook",
            params={"From": "whatsapp:+91"},
            signature="bad_sig",
        )
    assert result is True


def test_verify_returns_false_for_invalid_signature():
    """In production, a wrong signature must return False."""
    with patch("app.core.security.settings") as mock_settings:
        mock_settings.validate_twilio_signature = True
        mock_settings.twilio_auth_token = "test_auth_token"
        result = verify_twilio_signature(
            url="https://example.com/webhook",
            params={"From": "whatsapp:+91"},
            signature="clearly_wrong_signature",
        )
    assert result is False


def test_verify_returns_true_for_correct_signature():
    """A properly signed request must pass verification."""
    from twilio.request_validator import RequestValidator

    auth_token = "test_auth_token_abc123"
    url = "https://example.com/webhook/whatsapp"
    params = {"From": "whatsapp:+919876543210", "Body": "Hello"}

    # Generate the correct signature the same way Twilio does
    validator = RequestValidator(auth_token)
    correct_sig = validator.compute_signature(url, params)

    with patch("app.core.security.settings") as mock_settings:
        mock_settings.validate_twilio_signature = True
        mock_settings.twilio_auth_token = auth_token
        result = verify_twilio_signature(url, params, correct_sig)

    assert result is True
