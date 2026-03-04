"""S11.7 — Seed Script.

Loads the drug database CSV and all glossary JSON files into Redis.

Usage:
    python backend/scripts/seed.py          # local
    python -m scripts.seed                  # from backend/ (Docker or local)

Reuses load_drug_csv() from S8.2 and load_glossary() from S6.2.
Connects to Redis using settings.REDIS_URL, runs both loaders,
logs summary counts, and returns 0 on success or 1 on failure.
"""

from __future__ import annotations

import asyncio
import sys
import time

import redis.asyncio as redis_asyncio
from loguru import logger

from backend.app.core.config import settings
from backend.app.services.drug_lookup import load_drug_csv
from backend.app.services.glossary import load_glossary


async def main() -> int:
    """Run seed: load drugs + glossary into Redis.

    Returns 0 on success, 1 on any failure.
    """
    start = time.monotonic()
    failed = False
    drug_count: int | None = None
    glossary_counts: dict[str, int] | None = None

    # ── Connect to Redis ─────────────────────────────────────────────────
    try:
        redis_client = redis_asyncio.from_url(settings.REDIS_URL)
    except Exception as exc:
        logger.error("Failed to connect to Redis: {}", exc)
        return 1

    try:
        # ── Load drug CSV ────────────────────────────────────────────────
        try:
            drug_count = await load_drug_csv(redis_client)
            logger.info("Drugs loaded: {} entries", drug_count)
        except Exception as exc:
            logger.error("Failed to load drug CSV: {}", exc)
            failed = True

        # ── Load glossary ────────────────────────────────────────────────
        try:
            glossary_counts = await load_glossary(redis_client)
            for lang, count in sorted(glossary_counts.items()):
                logger.info("Glossary loaded: {} — {} terms", lang, count)
        except Exception as exc:
            logger.error("Failed to load glossary: {}", exc)
            failed = True

        # ── Summary ──────────────────────────────────────────────────────
        elapsed = time.monotonic() - start
        total_glossary = sum(glossary_counts.values()) if glossary_counts else 0
        logger.info(
            "Seed complete: {} drugs, {} glossary terms ({} languages) in {:.2f}s",
            drug_count if drug_count is not None else 0,
            total_glossary,
            len(glossary_counts) if glossary_counts else 0,
            elapsed,
        )
    finally:
        await redis_client.aclose()

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
