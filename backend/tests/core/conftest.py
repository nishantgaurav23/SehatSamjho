"""Conftest for core tests — ensures env vars exist for module-level Settings()."""

import os

# These must be set BEFORE backend.app.core.config is imported,
# because `settings = Settings()` runs at module level (fail-fast design).
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
}

for _key, _val in _TEST_ENV.items():
    os.environ.setdefault(_key, _val)
