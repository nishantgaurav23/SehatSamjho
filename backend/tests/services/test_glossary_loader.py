"""S6.2 — GlossaryLoader + load_glossary() tests.

25 tests covering: constants & imports, constructor, _load_language_file,
load_all, load_glossary convenience function, and integration-style roundtrips.
"""

import asyncio
import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.models.schemas import GlossaryEntry


# ---------------------------------------------------------------------------
# Constants & imports (pure, no mocking) — tests 1–6
# ---------------------------------------------------------------------------


class TestConstantsAndImports:
    """Verify module is importable and exports expected symbols."""

    def test_glossary_module_importable(self):
        """Test 1: Module imports without error."""
        from backend.app.services import glossary  # noqa: F401

    def test_glossary_dir_is_path(self):
        """Test 2: GLOSSARY_DIR is a pathlib.Path."""
        from backend.app.services.glossary import GLOSSARY_DIR

        assert isinstance(GLOSSARY_DIR, Path)

    def test_glossary_dir_points_to_data_glossary(self):
        """Test 3: GLOSSARY_DIR path ends with data/glossary."""
        from backend.app.services.glossary import GLOSSARY_DIR

        parts = GLOSSARY_DIR.parts
        assert parts[-2] == "data"
        assert parts[-1] == "glossary"

    def test_glossary_redis_prefix_value(self):
        """Test 4: GLOSSARY_REDIS_PREFIX is 'glossary:'."""
        from backend.app.services.glossary import GLOSSARY_REDIS_PREFIX

        assert GLOSSARY_REDIS_PREFIX == "glossary:"

    def test_glossary_loader_class_exists(self):
        """Test 5: GlossaryLoader is a class."""
        from backend.app.services.glossary import GlossaryLoader

        assert inspect.isclass(GlossaryLoader)

    def test_load_glossary_function_exists(self):
        """Test 6: load_glossary is an async callable."""
        from backend.app.services.glossary import load_glossary

        assert callable(load_glossary)
        assert asyncio.iscoroutinefunction(load_glossary)


# ---------------------------------------------------------------------------
# GlossaryLoader constructor — tests 7–9
# ---------------------------------------------------------------------------


class TestGlossaryLoaderConstructor:
    """Verify constructor accepts redis_client and optional glossary_dir."""

    def test_loader_accepts_redis_client(self):
        """Test 7: Constructor takes redis_client param and stores it."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis)
        assert loader._redis is mock_redis

    def test_loader_accepts_optional_glossary_dir(self):
        """Test 8: Constructor takes optional glossary_dir param."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        custom_dir = Path("/tmp/custom_glossary")
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=custom_dir)
        assert loader._glossary_dir == custom_dir

    def test_loader_defaults_to_glossary_dir(self):
        """Test 9: When glossary_dir not provided, uses GLOSSARY_DIR."""
        from backend.app.services.glossary import GLOSSARY_DIR, GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis)
        assert loader._glossary_dir == GLOSSARY_DIR


# ---------------------------------------------------------------------------
# _load_language_file (mocked Redis) — tests 10–16
# ---------------------------------------------------------------------------


class TestLoadLanguageFile:
    """Verify _load_language_file reads JSON and loads into Redis hashes."""

    @pytest.fixture()
    def glossary_dir(self, tmp_path: Path) -> Path:
        """Create a temp glossary directory with a valid hi.json."""
        data = [
            {
                "term": "Hypertension",
                "explanation": "high blood pressure",
                "vernacular": "उच्च रक्तचाप",
            },
            {"term": "Diabetes", "explanation": "high blood sugar", "vernacular": "मधुमेह"},
        ]
        (tmp_path / "hi.json").write_text(json.dumps(data), encoding="utf-8")
        return tmp_path

    @pytest.mark.asyncio()
    async def test_load_language_file_calls_hset(self, glossary_dir: Path):
        """Test 10: Loads entries into correct Redis hash key."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=glossary_dir)
        await loader._load_language_file("hi")

        # hset should be called for each entry
        assert mock_redis.hset.await_count == 2
        # First call should use key "glossary:hi"
        first_call = mock_redis.hset.await_args_list[0]
        assert first_call[0][0] == "glossary:hi"

    @pytest.mark.asyncio()
    async def test_load_language_file_lowercase_keys(self, glossary_dir: Path):
        """Test 11: Term keys are lowercased in Redis."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=glossary_dir)
        await loader._load_language_file("hi")

        # Collect all field names (2nd positional arg to hset)
        fields = [call[0][1] for call in mock_redis.hset.await_args_list]
        assert "hypertension" in fields
        assert "diabetes" in fields
        # Must be lowercase
        for f in fields:
            assert f == f.lower()

    @pytest.mark.asyncio()
    async def test_load_language_file_values_are_json(self, glossary_dir: Path):
        """Test 12: Values stored are valid JSON strings."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=glossary_dir)
        await loader._load_language_file("hi")

        for call in mock_redis.hset.await_args_list:
            value = call[0][2]
            parsed = json.loads(value)
            assert "term" in parsed
            assert "explanation" in parsed
            assert "vernacular" in parsed

    @pytest.mark.asyncio()
    async def test_load_language_file_returns_count(self, glossary_dir: Path):
        """Test 13: Returns number of entries loaded."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=glossary_dir)
        count = await loader._load_language_file("hi")
        assert count == 2

    @pytest.mark.asyncio()
    async def test_load_language_file_file_not_found(self, tmp_path: Path):
        """Test 14: Raises FileNotFoundError for missing file."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            await loader._load_language_file("nonexistent")

    @pytest.mark.asyncio()
    async def test_load_language_file_invalid_json(self, tmp_path: Path):
        """Test 15: Raises error for malformed JSON."""
        (tmp_path / "bad.json").write_text("not valid json {{{", encoding="utf-8")

        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=tmp_path)
        with pytest.raises(json.JSONDecodeError):
            await loader._load_language_file("bad")

    @pytest.mark.asyncio()
    async def test_load_language_file_skips_invalid_entry(self, tmp_path: Path):
        """Test 16: Invalid Pydantic entries skipped with warning, valid ones loaded."""
        data = [
            {"term": "fever", "explanation": "high temp", "vernacular": "बुखार"},
            {"term": "", "explanation": "", "vernacular": ""},  # invalid: min_length=1 fails
            {"term": "cough", "explanation": "lung irritation", "vernacular": "खांसी"},
        ]
        (tmp_path / "hi.json").write_text(json.dumps(data), encoding="utf-8")

        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=tmp_path)
        count = await loader._load_language_file("hi")

        # Only 2 valid entries loaded, invalid one skipped
        assert count == 2
        assert mock_redis.hset.await_count == 2


# ---------------------------------------------------------------------------
# load_all (mocked Redis + temp directory) — tests 17–21
# ---------------------------------------------------------------------------


class TestLoadAll:
    """Verify load_all discovers and loads all JSON files."""

    @pytest.fixture()
    def multi_lang_dir(self, tmp_path: Path) -> Path:
        """Create temp dir with 3 language files."""
        for lang in ("hi", "ta", "bn"):
            data = [
                {"term": "fever", "explanation": "high temp", "vernacular": f"v_{lang}"},
                {"term": "cough", "explanation": "lung issue", "vernacular": f"c_{lang}"},
            ]
            (tmp_path / f"{lang}.json").write_text(json.dumps(data), encoding="utf-8")
        return tmp_path

    @pytest.mark.asyncio()
    async def test_load_all_discovers_json_files(self, multi_lang_dir: Path):
        """Test 17: Finds all .json files in directory."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=multi_lang_dir)
        result = await loader.load_all()

        assert set(result.keys()) == {"hi", "ta", "bn"}

    @pytest.mark.asyncio()
    async def test_load_all_returns_lang_count_dict(self, multi_lang_dir: Path):
        """Test 18: Returns {lang_code: count} mapping."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=multi_lang_dir)
        result = await loader.load_all()

        assert isinstance(result, dict)
        for lang, count in result.items():
            assert isinstance(lang, str)
            assert isinstance(count, int)
            assert count == 2

    @pytest.mark.asyncio()
    async def test_load_all_empty_directory(self, tmp_path: Path):
        """Test 19: Returns empty dict for empty directory."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=tmp_path)
        result = await loader.load_all()

        assert result == {}

    @pytest.mark.asyncio()
    async def test_load_all_partial_failure(self, tmp_path: Path):
        """Test 20: One bad file doesn't stop others from loading."""
        # Valid file
        valid_data = [{"term": "fever", "explanation": "high temp", "vernacular": "बुखार"}]
        (tmp_path / "hi.json").write_text(json.dumps(valid_data), encoding="utf-8")
        # Bad file
        (tmp_path / "bad.json").write_text("not json!!!", encoding="utf-8")

        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=tmp_path)
        result = await loader.load_all()

        # hi loaded successfully, bad failed
        assert "hi" in result
        assert result["hi"] == 1
        assert "bad" not in result

    @pytest.mark.asyncio()
    async def test_load_all_logs_summary(self, multi_lang_dir: Path):
        """Test 21: Logs total languages and terms loaded."""
        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=multi_lang_dir)

        with patch("backend.app.services.glossary.logger") as mock_logger:
            await loader.load_all()

            # Should log a summary with total languages and terms
            log_messages = " ".join(str(call) for call in mock_logger.info.call_args_list)
            assert "3" in log_messages  # 3 languages
            assert "6" in log_messages  # 6 total terms


# ---------------------------------------------------------------------------
# load_glossary convenience function — tests 22–23
# ---------------------------------------------------------------------------


class TestLoadGlossaryFunction:
    """Verify the module-level load_glossary() convenience wrapper."""

    @pytest.mark.asyncio()
    async def test_load_glossary_delegates_to_loader(self):
        """Test 22: Creates GlossaryLoader and calls load_all."""
        from backend.app.services.glossary import load_glossary

        mock_redis = AsyncMock()
        expected = {"hi": 25, "ta": 25}

        with patch("backend.app.services.glossary.GlossaryLoader") as MockLoader:
            mock_instance = AsyncMock()
            mock_instance.load_all.return_value = expected
            MockLoader.return_value = mock_instance

            result = await load_glossary(mock_redis)

            MockLoader.assert_called_once_with(mock_redis)
            mock_instance.load_all.assert_awaited_once()
            assert result == expected

    @pytest.mark.asyncio()
    async def test_load_glossary_returns_dict(self):
        """Test 23: Returns the same dict as load_all."""
        from backend.app.services.glossary import load_glossary

        mock_redis = AsyncMock()

        with patch("backend.app.services.glossary.GlossaryLoader") as MockLoader:
            mock_instance = AsyncMock()
            mock_instance.load_all.return_value = {"bn": 10}
            MockLoader.return_value = mock_instance

            result = await load_glossary(mock_redis)

            assert isinstance(result, dict)
            assert result == {"bn": 10}


# ---------------------------------------------------------------------------
# Integration-style (temp files + mock Redis) — tests 24–25
# ---------------------------------------------------------------------------


class TestIntegrationStyle:
    """Roundtrip validation: stored JSON → parseable GlossaryEntry."""

    @pytest.mark.asyncio()
    async def test_roundtrip_entry_is_valid_glossary_entry(self, tmp_path: Path):
        """Test 24: Stored JSON can be parsed back into GlossaryEntry."""
        data = [
            {
                "term": "Hypertension",
                "explanation": "high blood pressure",
                "vernacular": "उच्च रक्तचाप",
            },
        ]
        (tmp_path / "hi.json").write_text(json.dumps(data), encoding="utf-8")

        from backend.app.services.glossary import GlossaryLoader

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=tmp_path)
        await loader._load_language_file("hi")

        # Extract the JSON value stored in Redis
        stored_json = mock_redis.hset.await_args_list[0][0][2]
        entry = GlossaryEntry.model_validate_json(stored_json)
        assert entry.term == "Hypertension"
        assert entry.explanation == "high blood pressure"
        assert entry.vernacular == "उच्च रक्तचाप"

    @pytest.mark.asyncio()
    async def test_load_real_glossary_files(self):
        """Test 25: Loads actual data/glossary/ files into mock Redis, verifies counts."""
        from backend.app.services.glossary import GLOSSARY_DIR, GlossaryLoader

        if not GLOSSARY_DIR.exists():
            pytest.skip("Glossary data directory not found")

        mock_redis = AsyncMock()
        loader = GlossaryLoader(redis_client=mock_redis, glossary_dir=GLOSSARY_DIR)
        result = await loader.load_all()

        # Should load all 6 languages
        assert len(result) == 6
        expected_langs = {"hi", "ta", "te", "kn", "bn", "mr"}
        assert set(result.keys()) == expected_langs
        # Each should have >= 25 entries (expanded from 25 to 100 in S11.6)
        for lang, count in result.items():
            assert count >= 25, f"{lang} has {count} entries, expected >= 25"
