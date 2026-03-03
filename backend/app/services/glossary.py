"""S6.2–S6.4 — Glossary: loader, lookup, and formatting.

Reads per-language glossary JSON files from data/glossary/ and loads them into
Redis as hash maps. Each language gets a Redis hash keyed as glossary:{lang_code},
where the field is the medical term (lowercased) and the value is the full entry
serialized as a JSON string.

Also provides format_glossary_context() — a pure function that formats matched
GlossaryEntry objects into a text block for injection into a translation prompt.
"""

import json
from pathlib import Path

from loguru import logger
from pydantic import ValidationError

from backend.app.models.schemas import GlossaryEntry

# ── FR-1: GLOSSARY_DIR constant ──────────────────────────────────────────────
GLOSSARY_DIR: Path = Path(__file__).resolve().parents[3] / "data" / "glossary"

# ── FR-2: GLOSSARY_REDIS_PREFIX constant ─────────────────────────────────────
GLOSSARY_REDIS_PREFIX: str = "glossary:"


# ── FR-3: GlossaryLoader class ───────────────────────────────────────────────
class GlossaryLoader:
    """Loads glossary JSON files into Redis hash maps."""

    def __init__(self, redis_client, glossary_dir: Path | None = None) -> None:
        self._redis = redis_client
        self._glossary_dir = glossary_dir if glossary_dir is not None else GLOSSARY_DIR

    # ── FR-4: _load_language_file() ──────────────────────────────────────────
    async def _load_language_file(self, lang_code: str) -> int:
        """Read a single JSON file and load its entries into a Redis hash.

        Returns the count of entries loaded.
        Raises FileNotFoundError if file missing, json.JSONDecodeError if malformed.
        Skips individual entries that fail Pydantic validation.
        """
        file_path = self._glossary_dir / f"{lang_code}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Glossary file not found: {file_path}")

        raw = file_path.read_text(encoding="utf-8")
        entries = json.loads(raw)

        redis_key = f"{GLOSSARY_REDIS_PREFIX}{lang_code}"
        loaded = 0

        for i, entry_dict in enumerate(entries):
            try:
                entry = GlossaryEntry.model_validate(entry_dict)
            except ValidationError as exc:
                logger.warning(
                    "Skipping invalid glossary entry {} in {}: {}",
                    i,
                    lang_code,
                    exc,
                )
                continue

            await self._redis.hset(redis_key, entry.term.lower(), entry.model_dump_json())
            loaded += 1

        logger.info("Loaded {} terms for language '{}'", loaded, lang_code)
        return loaded

    # ── FR-5: load_all() ─────────────────────────────────────────────────────
    async def load_all(self) -> dict[str, int]:
        """Load all supported language glossary files into Redis.

        Returns dict mapping lang_code → count of entries loaded.
        """
        if not self._glossary_dir.exists():
            logger.warning("Glossary directory does not exist: {}", self._glossary_dir)
            return {}

        json_files = sorted(self._glossary_dir.glob("*.json"))
        if not json_files:
            logger.warning("No glossary JSON files found in {}", self._glossary_dir)
            return {}

        results: dict[str, int] = {}
        for json_file in json_files:
            lang_code = json_file.stem
            try:
                count = await self._load_language_file(lang_code)
                results[lang_code] = count
            except Exception as exc:
                logger.error("Failed to load glossary for '{}': {}", lang_code, exc)

        total_langs = len(results)
        total_terms = sum(results.values())
        logger.info(
            "Glossary loading complete: {} languages, {} total terms",
            total_langs,
            total_terms,
        )
        return results


# ── FR-6: load_glossary() module-level function ──────────────────────────────
async def load_glossary(redis_client) -> dict[str, int]:
    """Convenience wrapper: create GlossaryLoader and call load_all()."""
    loader = GlossaryLoader(redis_client)
    return await loader.load_all()


# ── S6.3: lookup_terms() ─────────────────────────────────────────────────────
async def lookup_terms(
    terms: list[str],
    language_code: str,
    redis_client,
) -> list[GlossaryEntry]:
    """Look up medical terms in the Redis glossary hash for a given language.

    Uses a single HMGET call for efficiency. Returns GlossaryEntry objects
    in the same order as the input terms (excluding misses and invalid entries).
    Gracefully handles Redis errors, invalid JSON, and Pydantic validation failures.
    """
    # FR-2: Normalize — strip, lowercase, drop blanks, deduplicate (preserve order)
    seen: set[str] = set()
    normalized: list[str] = []
    for t in terms:
        key = t.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(key)

    if not normalized:
        return []

    # FR-3: Single HMGET round-trip
    redis_key = f"{GLOSSARY_REDIS_PREFIX}{language_code}"
    try:
        values = await redis_client.hmget(redis_key, normalized)
    except Exception:
        logger.warning(
            "Redis error during glossary lookup for language '{}' ({} terms)",
            language_code,
            len(normalized),
        )
        return []

    # FR-5: Parse results maintaining input order
    entries: list[GlossaryEntry] = []
    for term, raw in zip(normalized, values):
        if raw is None:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "Invalid JSON for glossary term '{}' in language '{}'",
                term,
                language_code,
            )
            continue
        try:
            entry = GlossaryEntry.model_validate(data)
        except ValidationError:
            logger.warning(
                "Pydantic validation failed for glossary term '{}' in language '{}'",
                term,
                language_code,
            )
            continue
        entries.append(entry)

    return entries


# ── S6.4: format_glossary_context() ──────────────────────────────────────────

_MAX_BLOCK_CHARS = 2000


def format_glossary_context(
    entries: list[GlossaryEntry],
    language_name: str,
) -> str:
    """Format glossary entries into a text block for the translation prompt.

    Pure function — no I/O, no async, no side effects.
    Returns empty string for empty input. Truncates to ~2000 chars if needed.
    """
    if not entries:
        return ""

    header = f"--- Medical Glossary ({language_name}) ---"
    footer = "---"

    lines: list[str] = []
    for entry in entries:
        line = f"Term: {entry.term} -> {language_name}: {entry.vernacular} ({entry.explanation})"
        lines.append(line)

    # Build full block and check budget
    full_block = "\n".join([header, *lines, footer])

    if len(full_block) <= _MAX_BLOCK_CHARS:
        return full_block

    # Truncate: drop entries from end until under budget
    kept: list[str] = []
    for i, line in enumerate(lines):
        omitted = len(lines) - (i + 1)
        omit_msg = f"... ({omitted} more terms omitted)" if omitted > 0 else ""
        candidate_parts = [header, *kept, line]
        if omit_msg:
            candidate_parts.append(omit_msg)
        candidate_parts.append(footer)
        candidate = "\n".join(candidate_parts)
        if len(candidate) > _MAX_BLOCK_CHARS:
            break
        kept.append(line)

    omitted = len(lines) - len(kept)
    parts = [header, *kept]
    if omitted > 0:
        parts.append(f"... ({omitted} more terms omitted)")
    parts.append(footer)
    return "\n".join(parts)
