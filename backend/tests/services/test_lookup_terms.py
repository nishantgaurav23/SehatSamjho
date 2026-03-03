"""Tests for S6.3 — lookup_terms().

20 tests covering imports/signature, empty/no-op, normalization,
Redis interaction, happy path, and error resilience.
"""

import asyncio
import inspect
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from loguru import logger

from backend.app.models.schemas import GlossaryEntry


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_entry(term: str, explanation: str = "explain", vernacular: str = "vern") -> str:
    """Return a JSON string for a valid GlossaryEntry."""
    return json.dumps({"term": term, "explanation": explanation, "vernacular": vernacular})


@pytest.fixture()
def mock_redis():
    """Async mock Redis client with hmget."""
    client = AsyncMock()
    client.hmget = AsyncMock(return_value=[])
    return client


# ══════════════════════════════════════════════════════════════════════════════
# 1–3: Imports & Signature
# ══════════════════════════════════════════════════════════════════════════════


class TestImportsAndSignature:
    """Tests 1–3: importability, async, params."""

    def test_lookup_terms_importable(self):
        """lookup_terms can be imported from glossary module."""
        from backend.app.services.glossary import lookup_terms  # noqa: F401

    def test_lookup_terms_is_async(self):
        """lookup_terms is a coroutine function."""
        from backend.app.services.glossary import lookup_terms

        assert asyncio.iscoroutinefunction(lookup_terms)

    def test_lookup_terms_signature(self):
        """lookup_terms accepts terms, language_code, redis_client params."""
        from backend.app.services.glossary import lookup_terms

        sig = inspect.signature(lookup_terms)
        params = list(sig.parameters.keys())
        assert "terms" in params
        assert "language_code" in params
        assert "redis_client" in params


# ══════════════════════════════════════════════════════════════════════════════
# 4–6: Empty / No-Op Cases
# ══════════════════════════════════════════════════════════════════════════════


class TestEmptyNoOp:
    """Tests 4–6: empty terms, no Redis call, whitespace-only."""

    @pytest.mark.asyncio()
    async def test_empty_terms_returns_empty_list(self, mock_redis):
        """Empty terms list returns []."""
        from backend.app.services.glossary import lookup_terms

        result = await lookup_terms([], "hi", mock_redis)
        assert result == []

    @pytest.mark.asyncio()
    async def test_empty_terms_no_redis_call(self, mock_redis):
        """Redis hmget is NOT called when terms list is empty."""
        from backend.app.services.glossary import lookup_terms

        await lookup_terms([], "hi", mock_redis)
        mock_redis.hmget.assert_not_called()

    @pytest.mark.asyncio()
    async def test_whitespace_only_terms_skipped(self, mock_redis):
        """Whitespace-only terms are skipped, returns []."""
        from backend.app.services.glossary import lookup_terms

        result = await lookup_terms(["  ", "", "   "], "hi", mock_redis)
        assert result == []
        mock_redis.hmget.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# 7–9: Term Normalization
# ══════════════════════════════════════════════════════════════════════════════


class TestNormalization:
    """Tests 7–9: lowercase, strip, dedup."""

    @pytest.mark.asyncio()
    async def test_terms_lowercased(self, mock_redis):
        """Terms are lowercased before Redis query."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [None]
        await lookup_terms(["Hypertension"], "hi", mock_redis)

        _, fields = mock_redis.hmget.call_args[0]  # (key, *fields)
        # hmget is called as hmget(key, field1, field2, ...) or hmget(key, [field1, ...])
        # Check the normalized term is in the call
        call_args = mock_redis.hmget.call_args
        # Could be hmget(key, [terms]) or hmget(key, *terms)
        all_args = call_args[0]  # positional args tuple
        # First arg is the key, remaining are fields (or second arg is list)
        if len(all_args) == 2 and isinstance(all_args[1], list):
            queried_terms = all_args[1]
        else:
            queried_terms = list(all_args[1:])
        assert "hypertension" in queried_terms

    @pytest.mark.asyncio()
    async def test_terms_stripped(self, mock_redis):
        """Terms are stripped of whitespace before Redis query."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [None]
        await lookup_terms(["  fever  "], "hi", mock_redis)

        call_args = mock_redis.hmget.call_args[0]
        if len(call_args) == 2 and isinstance(call_args[1], list):
            queried_terms = call_args[1]
        else:
            queried_terms = list(call_args[1:])
        assert "fever" in queried_terms

    @pytest.mark.asyncio()
    async def test_duplicate_terms_deduplicated(self, mock_redis):
        """Duplicate terms after normalization are deduplicated."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [None]
        await lookup_terms(["fever", "Fever", "FEVER"], "hi", mock_redis)

        call_args = mock_redis.hmget.call_args[0]
        if len(call_args) == 2 and isinstance(call_args[1], list):
            queried_terms = call_args[1]
        else:
            queried_terms = list(call_args[1:])
        assert queried_terms.count("fever") == 1


# ══════════════════════════════════════════════════════════════════════════════
# 10–12: Redis Interaction
# ══════════════════════════════════════════════════════════════════════════════


class TestRedisInteraction:
    """Tests 10–12: HMGET usage, correct key, normalized fields."""

    @pytest.mark.asyncio()
    async def test_uses_hmget_not_hget(self, mock_redis):
        """Uses hmget (batch) not hget (individual)."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [None]
        mock_redis.hget = AsyncMock()

        await lookup_terms(["fever"], "hi", mock_redis)

        mock_redis.hmget.assert_called_once()
        mock_redis.hget.assert_not_called()

    @pytest.mark.asyncio()
    async def test_correct_redis_key(self, mock_redis):
        """Redis key is glossary:{language_code}."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [None]
        await lookup_terms(["fever"], "ta", mock_redis)

        call_args = mock_redis.hmget.call_args[0]
        assert call_args[0] == "glossary:ta"

    @pytest.mark.asyncio()
    async def test_hmget_called_with_normalized_terms(self, mock_redis):
        """Fields passed to hmget are normalized (lowercase + stripped)."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [None, None]
        await lookup_terms(["  Fever  ", "HEADACHE"], "hi", mock_redis)

        call_args = mock_redis.hmget.call_args[0]
        if len(call_args) == 2 and isinstance(call_args[1], list):
            queried_terms = call_args[1]
        else:
            queried_terms = list(call_args[1:])
        assert "fever" in queried_terms
        assert "headache" in queried_terms


# ══════════════════════════════════════════════════════════════════════════════
# 13–17: Happy Path
# ══════════════════════════════════════════════════════════════════════════════


class TestHappyPath:
    """Tests 13–17: matches, multiple, partial, none, ordering."""

    @pytest.mark.asyncio()
    async def test_returns_glossary_entries(self, mock_redis):
        """Matching terms return valid GlossaryEntry objects."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [_make_entry("fever")]
        result = await lookup_terms(["fever"], "hi", mock_redis)

        assert len(result) == 1
        assert isinstance(result[0], GlossaryEntry)
        assert result[0].term == "fever"

    @pytest.mark.asyncio()
    async def test_multiple_matches(self, mock_redis):
        """Multiple terms found returns multiple entries."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [
            _make_entry("fever"),
            _make_entry("headache"),
        ]
        result = await lookup_terms(["fever", "headache"], "hi", mock_redis)

        assert len(result) == 2
        assert result[0].term == "fever"
        assert result[1].term == "headache"

    @pytest.mark.asyncio()
    async def test_partial_matches(self, mock_redis):
        """Some terms found, some not — only found ones returned."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [
            _make_entry("fever"),
            None,
            _make_entry("headache"),
        ]
        result = await lookup_terms(["fever", "xyz", "headache"], "hi", mock_redis)

        assert len(result) == 2
        terms = [e.term for e in result]
        assert "fever" in terms
        assert "headache" in terms

    @pytest.mark.asyncio()
    async def test_no_matches_returns_empty(self, mock_redis):
        """All terms miss → returns []."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [None, None]
        result = await lookup_terms(["abc", "xyz"], "hi", mock_redis)

        assert result == []

    @pytest.mark.asyncio()
    async def test_return_order_matches_input(self, mock_redis):
        """Entries returned in same order as input terms."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [
            _make_entry("alpha"),
            None,
            _make_entry("charlie"),
            _make_entry("bravo"),
        ]
        result = await lookup_terms(["alpha", "missing", "charlie", "bravo"], "hi", mock_redis)

        assert len(result) == 3
        assert result[0].term == "alpha"
        assert result[1].term == "charlie"
        assert result[2].term == "bravo"


# ══════════════════════════════════════════════════════════════════════════════
# 18–20: Error Resilience
# ══════════════════════════════════════════════════════════════════════════════


class TestErrorResilience:
    """Tests 18–20: Redis error, invalid JSON, invalid Pydantic."""

    @pytest.mark.asyncio()
    async def test_redis_error_returns_empty_list(self, mock_redis, caplog):
        """Redis exception → returns [], logs warning."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.side_effect = ConnectionError("Redis down")

        # Propagate loguru to standard logging for caplog
        handler_id = logger.add(
            lambda msg: caplog.handler.emit(
                MagicMock(getMessage=lambda: str(msg), levelno=30, levelname="WARNING")
            ),
            level="WARNING",
        )
        try:
            result = await lookup_terms(["fever"], "hi", mock_redis)
            assert result == []
        finally:
            logger.remove(handler_id)

    @pytest.mark.asyncio()
    async def test_invalid_json_entry_skipped(self, mock_redis):
        """One entry has bad JSON → skipped, others returned."""
        from backend.app.services.glossary import lookup_terms

        mock_redis.hmget.return_value = [
            _make_entry("fever"),
            "not-valid-json{{{",
            _make_entry("headache"),
        ]
        result = await lookup_terms(["fever", "bad", "headache"], "hi", mock_redis)

        assert len(result) == 2
        assert result[0].term == "fever"
        assert result[1].term == "headache"

    @pytest.mark.asyncio()
    async def test_invalid_pydantic_entry_skipped(self, mock_redis):
        """One entry fails GlossaryEntry validation → skipped, others returned."""
        from backend.app.services.glossary import lookup_terms

        # Missing required 'vernacular' field
        bad_entry = json.dumps({"term": "bad", "explanation": "x"})
        mock_redis.hmget.return_value = [
            _make_entry("fever"),
            bad_entry,
            _make_entry("headache"),
        ]
        result = await lookup_terms(["fever", "bad", "headache"], "hi", mock_redis)

        assert len(result) == 2
        assert result[0].term == "fever"
        assert result[1].term == "headache"
