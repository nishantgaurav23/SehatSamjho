"""S11.7 — Seed Script tests.

20 tests covering: importability, async main, __init__.py, Redis connection,
load_drug_csv call, load_glossary call, logging, exit codes, partial failure,
call order, Makefile targets.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MAKEFILE = ROOT / "Makefile"


# ══════════════════════════════════════════════════════════════════════════════
# 1–3: Importability & structure
# ══════════════════════════════════════════════════════════════════════════════


class TestSeedModuleStructure:
    """Tests 1–3: module importable, main async, __init__.py exists."""

    def test_seed_module_importable(self):
        """Test 1: backend.scripts.seed can be imported."""
        import backend.scripts.seed  # noqa: F401

    def test_seed_has_main_function(self):
        """Test 2: main() exists and is a coroutine function."""
        from backend.scripts.seed import main

        assert callable(main)
        assert asyncio.iscoroutinefunction(main), "main() must be async"

    def test_seed_init_exists(self):
        """Test 3: backend/scripts/__init__.py exists."""
        init_path = BACKEND / "scripts" / "__init__.py"
        assert init_path.exists(), f"Expected {init_path} to exist"


# ══════════════════════════════════════════════════════════════════════════════
# 4: Redis connection
# ══════════════════════════════════════════════════════════════════════════════


class TestSeedRedisConnection:
    """Test 4: main() creates a Redis connection from settings."""

    @pytest.mark.asyncio
    async def test_seed_connects_to_redis(self):
        """Test 4: main() calls redis.asyncio.from_url with settings.REDIS_URL."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", new_callable=AsyncMock, return_value=10),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                return_value={"hi": 5},
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
        ):
            mock_settings.REDIS_URL = "redis://testhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            code = await main()

            mock_redis_mod.from_url.assert_called_once_with("redis://testhost:6379/0")
            assert code == 0


# ══════════════════════════════════════════════════════════════════════════════
# 5–6: Loader calls
# ══════════════════════════════════════════════════════════════════════════════


class TestSeedLoaderCalls:
    """Tests 5–6: main() calls load_drug_csv and load_glossary."""

    @pytest.mark.asyncio
    async def test_seed_calls_load_drug_csv(self):
        """Test 5: main() calls load_drug_csv(redis_client)."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()
        mock_load_drug = AsyncMock(return_value=66)
        mock_load_glossary = AsyncMock(return_value={"hi": 100})

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", mock_load_drug),
            patch("backend.scripts.seed.load_glossary", mock_load_glossary),
            patch("backend.scripts.seed.settings") as mock_settings,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            await main()

            mock_load_drug.assert_called_once_with(mock_redis)

    @pytest.mark.asyncio
    async def test_seed_calls_load_glossary(self):
        """Test 6: main() calls load_glossary(redis_client)."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()
        mock_load_drug = AsyncMock(return_value=66)
        mock_load_glossary = AsyncMock(return_value={"hi": 100})

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", mock_load_drug),
            patch("backend.scripts.seed.load_glossary", mock_load_glossary),
            patch("backend.scripts.seed.settings") as mock_settings,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            await main()

            mock_load_glossary.assert_called_once_with(mock_redis)


# ══════════════════════════════════════════════════════════════════════════════
# 7–10: Logging
# ══════════════════════════════════════════════════════════════════════════════


class TestSeedLogging:
    """Tests 7–10: drug count, glossary counts, total summary, elapsed time."""

    @pytest.mark.asyncio
    async def test_seed_logs_drug_count(self, capsys):
        """Test 7: After load_drug_csv, logs the drug count."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", new_callable=AsyncMock, return_value=66),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                return_value={"hi": 100},
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
            patch("backend.scripts.seed.logger") as mock_logger,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            await main()

            # Check that at least one info/success call mentions "66" (the drug count)
            all_calls = [str(c) for c in mock_logger.info.call_args_list]
            joined = " ".join(all_calls)
            assert "66" in joined, f"Expected drug count 66 in logs: {joined}"

    @pytest.mark.asyncio
    async def test_seed_logs_glossary_counts(self):
        """Test 8: After load_glossary, logs per-language counts."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", new_callable=AsyncMock, return_value=10),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                return_value={"hi": 100, "ta": 80},
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
            patch("backend.scripts.seed.logger") as mock_logger,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            await main()

            all_calls = " ".join(str(c) for c in mock_logger.info.call_args_list)
            assert "hi" in all_calls, f"Expected 'hi' in glossary log: {all_calls}"
            assert "100" in all_calls, f"Expected '100' in glossary log: {all_calls}"

    @pytest.mark.asyncio
    async def test_seed_logs_total_summary(self):
        """Test 9: Logs a total summary line."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", new_callable=AsyncMock, return_value=66),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                return_value={"hi": 100, "ta": 80},
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
            patch("backend.scripts.seed.logger") as mock_logger,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            await main()

            # Look for a summary call with total glossary terms (180)
            all_calls = " ".join(str(c) for c in mock_logger.info.call_args_list)
            assert "180" in all_calls, f"Expected total 180 in summary: {all_calls}"

    @pytest.mark.asyncio
    async def test_seed_logs_elapsed_time(self):
        """Test 10: Summary includes elapsed time."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", new_callable=AsyncMock, return_value=10),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                return_value={"hi": 5},
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
            patch("backend.scripts.seed.logger") as mock_logger,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            await main()

            # The summary log call should contain a float arg (elapsed seconds)
            # and format string with {:.2f}s
            summary_calls = [c for c in mock_logger.info.call_args_list if "2f}s" in str(c)]
            assert len(summary_calls) >= 1, (
                f"Expected summary log with elapsed time format: "
                f"{mock_logger.info.call_args_list}"
            )
            # The last positional arg should be a float (elapsed time)
            last_arg = summary_calls[0][0][-1]
            assert isinstance(
                last_arg, float
            ), f"Elapsed time should be float, got {type(last_arg)}"


# ══════════════════════════════════════════════════════════════════════════════
# 11–12: Redis close
# ══════════════════════════════════════════════════════════════════════════════


class TestSeedRedisClose:
    """Tests 11–12: Redis aclose() called on success and failure."""

    @pytest.mark.asyncio
    async def test_seed_closes_redis_on_success(self):
        """Test 11: Redis .aclose() called after successful run."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", new_callable=AsyncMock, return_value=10),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                return_value={"hi": 5},
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            await main()

            mock_redis.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_seed_closes_redis_on_failure(self):
        """Test 12: Redis .aclose() called even when a loader fails."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch(
                "backend.scripts.seed.load_drug_csv",
                new_callable=AsyncMock,
                side_effect=RuntimeError("CSV broken"),
            ),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                return_value={"hi": 5},
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            await main()

            mock_redis.aclose.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# 13–16: Exit codes
# ══════════════════════════════════════════════════════════════════════════════


class TestSeedExitCodes:
    """Tests 13–16: exit codes 0 on success, 1 on various failures."""

    @pytest.mark.asyncio
    async def test_seed_exits_zero_on_success(self):
        """Test 13: Returns 0 when both loaders succeed."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", new_callable=AsyncMock, return_value=10),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                return_value={"hi": 5},
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            code = await main()
            assert code == 0

    @pytest.mark.asyncio
    async def test_seed_exits_one_on_drug_failure(self):
        """Test 14: Returns 1 when load_drug_csv raises."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch(
                "backend.scripts.seed.load_drug_csv",
                new_callable=AsyncMock,
                side_effect=FileNotFoundError("CSV missing"),
            ),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                return_value={"hi": 5},
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            code = await main()
            assert code == 1

    @pytest.mark.asyncio
    async def test_seed_exits_one_on_glossary_failure(self):
        """Test 15: Returns 1 when load_glossary raises."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", new_callable=AsyncMock, return_value=10),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                side_effect=RuntimeError("JSON broken"),
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            code = await main()
            assert code == 1

    @pytest.mark.asyncio
    async def test_seed_exits_one_on_redis_connection_failure(self):
        """Test 16: Returns 1 when Redis connection itself fails."""
        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.settings") as mock_settings,
        ):
            mock_settings.REDIS_URL = "redis://badhost:6379/0"
            mock_redis_mod.from_url.side_effect = ConnectionError("Cannot connect")

            from backend.scripts.seed import main

            code = await main()
            assert code == 1


# ══════════════════════════════════════════════════════════════════════════════
# 17–18: Partial failure & call order
# ══════════════════════════════════════════════════════════════════════════════


class TestSeedPartialFailureAndOrder:
    """Tests 17–18: partial failure logging, call order."""

    @pytest.mark.asyncio
    async def test_seed_partial_failure_logs_success(self):
        """Test 17: If drugs succeed but glossary fails, drug count is still logged."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", new_callable=AsyncMock, return_value=42),
            patch(
                "backend.scripts.seed.load_glossary",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Glossary broken"),
            ),
            patch("backend.scripts.seed.settings") as mock_settings,
            patch("backend.scripts.seed.logger") as mock_logger,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            code = await main()
            assert code == 1

            # Drug count should still appear in logs
            all_calls = " ".join(str(c) for c in mock_logger.info.call_args_list)
            assert "42" in all_calls, f"Expected drug count 42 in logs: {all_calls}"

    @pytest.mark.asyncio
    async def test_seed_calls_loaders_in_order(self):
        """Test 18: Drugs loaded before glossary (both called)."""
        mock_redis = AsyncMock()
        mock_redis.aclose = AsyncMock()

        call_order = []

        async def mock_load_drug(redis_client):
            call_order.append("drug")
            return 10

        async def mock_load_glossary(redis_client):
            call_order.append("glossary")
            return {"hi": 5}

        with (
            patch("backend.scripts.seed.redis_asyncio") as mock_redis_mod,
            patch("backend.scripts.seed.load_drug_csv", side_effect=mock_load_drug),
            patch("backend.scripts.seed.load_glossary", side_effect=mock_load_glossary),
            patch("backend.scripts.seed.settings") as mock_settings,
        ):
            mock_settings.REDIS_URL = "redis://localhost:6379/0"
            mock_redis_mod.from_url.return_value = mock_redis

            from backend.scripts.seed import main

            await main()

            assert call_order == ["drug", "glossary"]


# ══════════════════════════════════════════════════════════════════════════════
# 19–20: Makefile targets
# ══════════════════════════════════════════════════════════════════════════════


class TestSeedMakefileTargets:
    """Tests 19–20: Makefile has local-seed and seed targets."""

    def test_makefile_local_seed_target(self):
        """Test 19: Makefile has a local-seed target."""
        content = MAKEFILE.read_text()
        assert re.search(
            r"^local-seed:", content, re.MULTILINE
        ), "Makefile must have a 'local-seed:' target"

    def test_makefile_seed_target_compatible(self):
        """Test 20: Existing seed target uses python -m scripts.seed."""
        content = MAKEFILE.read_text()
        # The seed target should reference scripts.seed
        assert "scripts.seed" in content, "seed target must reference scripts.seed"
