"""S3.4 — Send Language Selection tests.

Tests for build_language_menu_text(), send_language_selection(), and send_more_languages().
17 tests covering pure functions, async sending, ContentSid fallback, and PHI-safe logging.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure test env vars are set BEFORE importing modules that read settings
# ---------------------------------------------------------------------------
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("TWILIO_ACCOUNT_SID", "ACtest1234567890")
os.environ.setdefault("TWILIO_AUTH_TOKEN", "test-auth-token")
os.environ.setdefault("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
os.environ.setdefault("BHASHINI_API_KEY", "test-bhashini-key")
os.environ.setdefault("BHASHINI_USER_ID", "test-bhashini-user")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-aws-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
os.environ.setdefault("S3_BUCKET", "test-bucket")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from backend.app.services.whatsapp import (
    SUPPORTED_LANGUAGES,
    TOP_LANGUAGES,
    build_language_menu_text,
    parse_language_selection,
    send_language_selection,
    send_more_languages,
)


# ===========================================================================
# build_language_menu_text() tests
# ===========================================================================


class TestBuildLanguageMenuText:
    """Tests for the pure build_language_menu_text() function."""

    def test_menu_text_has_nine_lines(self) -> None:
        """Output has exactly 9 lines (8 languages + More)."""
        text = build_language_menu_text()
        lines = text.strip().split("\n")
        assert len(lines) == 9

    def test_menu_text_first_line_hindi(self) -> None:
        """First line is '1. Hindi (हिन्दी)'."""
        text = build_language_menu_text()
        first_line = text.strip().split("\n")[0]
        assert first_line == "1. Hindi (हिन्दी)"

    def test_menu_text_last_line_more(self) -> None:
        """Last line is '9. More languages'."""
        text = build_language_menu_text()
        last_line = text.strip().split("\n")[-1]
        assert last_line == "9. More languages"

    def test_menu_text_all_top_languages_present(self) -> None:
        """All 8 TOP_LANGUAGES appear in correct order."""
        text = build_language_menu_text()
        lines = text.strip().split("\n")
        for i, code in enumerate(TOP_LANGUAGES):
            lang = SUPPORTED_LANGUAGES[code]
            expected = f"{i + 1}. {lang['name']} ({lang['display_name']})"
            assert lines[i] == expected, f"Line {i + 1} mismatch: {lines[i]} != {expected}"

    def test_menu_text_numbering_matches_parse(self) -> None:
        """Numbers 1-8 correspond to the same languages parse_language_selection() resolves."""
        text = build_language_menu_text()
        lines = text.strip().split("\n")
        for i in range(8):
            # Parse the number from the line
            num_str = str(i + 1)
            result = parse_language_selection(num_str)
            assert result is not None, f"parse_language_selection('{num_str}') returned None"
            lang_name, lang_code = result
            # Verify the line contains this language name
            assert lang_name in lines[i], f"Line {i + 1} should contain '{lang_name}'"


# ===========================================================================
# send_language_selection() tests
# ===========================================================================


class TestSendLanguageSelection:
    """Tests for the async send_language_selection() function."""

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_text_message", new_callable=AsyncMock)
    async def test_send_language_selection_text_fallback(self, mock_send: AsyncMock) -> None:
        """When no ContentSid configured, calls send_text_message() with menu text."""
        mock_send.return_value = "SM_MENU_123"

        await send_language_selection("whatsapp:+919876543210")

        mock_send.assert_awaited_once()
        call_args = mock_send.call_args
        body = call_args[1].get("body") or call_args[0][1]
        # Body should contain the language menu
        assert "Hindi" in body
        assert "More languages" in body

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_text_message", new_callable=AsyncMock)
    async def test_send_language_selection_returns_sid(self, mock_send: AsyncMock) -> None:
        """Returns the message SID from the underlying send call."""
        mock_send.return_value = "SM_MENU_456"

        result = await send_language_selection("whatsapp:+919876543210")

        assert result == "SM_MENU_456"

    @pytest.mark.asyncio
    async def test_send_language_selection_empty_to_raises(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError):
            await send_language_selection("")

    @pytest.mark.asyncio
    async def test_send_language_selection_whitespace_to_raises(self) -> None:
        """Whitespace-only string raises ValueError."""
        with pytest.raises(ValueError):
            await send_language_selection("   ")

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.asyncio.to_thread")
    @patch("backend.app.services.whatsapp._get_twilio_client")
    @patch("backend.app.services.whatsapp.send_text_message", new_callable=AsyncMock)
    async def test_send_language_selection_content_sid_fallback(
        self,
        mock_send: AsyncMock,
        mock_get_client: MagicMock,
        mock_to_thread: MagicMock,
    ) -> None:
        """If ContentSid send fails, falls back to text list."""
        from twilio.base.exceptions import TwilioRestException

        # Simulate ContentSid being set
        with patch(
            "backend.app.services.whatsapp.settings",
            create=True,
        ) as mock_settings:
            mock_settings.TWILIO_CONTENT_SID = "HX_TEST_CONTENT_SID"
            mock_settings.TWILIO_WHATSAPP_FROM = "whatsapp:+14155238886"

            # ContentSid path fails
            mock_to_thread.side_effect = TwilioRestException(
                status=400, uri="/test", msg="ContentSid failed"
            )

            # Fallback path succeeds
            mock_send.return_value = "SM_FALLBACK"

            result = await send_language_selection("whatsapp:+919876543210")

            assert result == "SM_FALLBACK"
            mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_text_message", new_callable=AsyncMock)
    async def test_send_language_selection_logs_hash_not_phone(self, mock_send: AsyncMock) -> None:
        """Log output contains hashed phone, not raw number."""
        from io import StringIO

        from loguru import logger

        mock_send.return_value = "SM_LOG_TEST"

        phone = "whatsapp:+919876543210"
        log_output = StringIO()
        handler_id = logger.add(log_output, format="{message}", level="DEBUG")

        try:
            await send_language_selection(phone)
            log_text = log_output.getvalue()

            # Raw phone should NOT appear
            assert "+919876543210" not in log_text
            assert phone not in log_text
        finally:
            logger.remove(handler_id)


# ===========================================================================
# send_more_languages() tests
# ===========================================================================


class TestSendMoreLanguages:
    """Tests for the async send_more_languages() function."""

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_text_message", new_callable=AsyncMock)
    async def test_send_more_languages_sends_14_languages(self, mock_send: AsyncMock) -> None:
        """Message body contains exactly 14 language entries."""
        mock_send.return_value = "SM_MORE_123"

        await send_more_languages("whatsapp:+919876543210")

        call_args = mock_send.call_args
        body = call_args[1].get("body") or call_args[0][1]
        # Count non-empty lines (excluding any header/footer)
        lang_lines = [line for line in body.strip().split("\n") if line.strip()]
        assert len(lang_lines) == 14

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_text_message", new_callable=AsyncMock)
    async def test_send_more_languages_excludes_top_8(self, mock_send: AsyncMock) -> None:
        """None of the TOP_LANGUAGES appear in the output."""
        mock_send.return_value = "SM_MORE_123"

        await send_more_languages("whatsapp:+919876543210")

        call_args = mock_send.call_args
        body = call_args[1].get("body") or call_args[0][1]

        top_names = [SUPPORTED_LANGUAGES[code]["name"] for code in TOP_LANGUAGES]
        for name in top_names:
            # Check that top language names don't appear as line starts
            for line in body.strip().split("\n"):
                # Each line format is "code: Name (display)" — check the name part
                if ": " in line:
                    line_name = line.split(": ")[1].split(" (")[0]
                    assert line_name != name, f"Top language '{name}' should not be in more list"

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_text_message", new_callable=AsyncMock)
    async def test_send_more_languages_sorted_alphabetically(self, mock_send: AsyncMock) -> None:
        """Languages are sorted by English name."""
        mock_send.return_value = "SM_MORE_123"

        await send_more_languages("whatsapp:+919876543210")

        call_args = mock_send.call_args
        body = call_args[1].get("body") or call_args[0][1]

        lines = [line for line in body.strip().split("\n") if line.strip()]
        names = []
        for line in lines:
            if ": " in line:
                name = line.split(": ")[1].split(" (")[0]
                names.append(name)

        assert names == sorted(names), f"Languages not sorted: {names}"

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_text_message", new_callable=AsyncMock)
    async def test_send_more_languages_uses_code_not_number(self, mock_send: AsyncMock) -> None:
        """Lines use language codes (e.g. 'as: Assamese') not numbers."""
        mock_send.return_value = "SM_MORE_123"

        await send_more_languages("whatsapp:+919876543210")

        call_args = mock_send.call_args
        body = call_args[1].get("body") or call_args[0][1]

        lines = [line for line in body.strip().split("\n") if line.strip()]
        for line in lines:
            # Each line should start with a language code followed by ":"
            assert ": " in line, f"Line should contain ': ' separator: {line}"
            prefix = line.split(":")[0].strip()
            # Prefix should NOT be a number
            assert not prefix.isdigit(), f"Line starts with number instead of code: {line}"
            # Prefix should be a valid language code
            assert prefix in SUPPORTED_LANGUAGES, f"'{prefix}' is not a valid language code"

    @pytest.mark.asyncio
    @patch("backend.app.services.whatsapp.send_text_message", new_callable=AsyncMock)
    async def test_send_more_languages_returns_sid(self, mock_send: AsyncMock) -> None:
        """Returns message SID."""
        mock_send.return_value = "SM_MORE_SID"

        result = await send_more_languages("whatsapp:+919876543210")

        assert result == "SM_MORE_SID"

    @pytest.mark.asyncio
    async def test_send_more_languages_empty_to_raises(self) -> None:
        """Empty string raises ValueError."""
        with pytest.raises(ValueError):
            await send_more_languages("")
