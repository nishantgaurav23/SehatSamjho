"""Drug lookup service — CSV (S8.2) + lookup (S8.3) + enrichment (S8.4) + API (S8.5).

S8.2: Reads the drug database CSV and loads entries into Redis.
S8.3: lookup_drug() checks Redis first, falls back to IndianMedicineDB API.
S8.4: enrich_prescription() runs concurrent lookups for all medicines in a prescription.
S8.5: _call_indianmedicinedb() — httpx async GET with tenacity retry.
"""

from __future__ import annotations

import asyncio
import csv
import json
import re
from pathlib import Path

import httpx
from loguru import logger
from pydantic import ValidationError
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from backend.app.models.schemas import DrugInfo, PrescriptionData

# ── FR-1: DRUG_CSV_PATH constant ─────────────────────────────────────────────
DRUG_CSV_PATH: Path = Path(__file__).resolve().parents[3] / "data" / "drugs" / "medicines.csv"

# ── FR-2: DRUG_REDIS_PREFIX constant ──────────────────────────────────────────
DRUG_REDIS_PREFIX: str = "drug:"


# ── FR-3: DrugCSVLoader class ─────────────────────────────────────────────────
class DrugCSVLoader:
    """Reads drug CSV and loads entries into Redis hash maps."""

    def __init__(self, redis_client, csv_path: Path | None = None) -> None:
        self._redis = redis_client
        self._csv_path = csv_path if csv_path is not None else DRUG_CSV_PATH

    # ── FR-4: _load_csv() ────────────────────────────────────────────────────
    async def _load_csv(self) -> int:
        """Read CSV, validate rows, store in Redis. Returns count of entries loaded."""
        if not self._csv_path.exists():
            raise FileNotFoundError(f"Drug CSV file not found: {self._csv_path}")

        loaded = 0

        with self._csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                try:
                    drug = DrugInfo.model_validate(row)
                except ValidationError as exc:
                    logger.warning(
                        "Skipping invalid drug row {}: {}",
                        i,
                        exc,
                    )
                    continue

                brand_key = f"{DRUG_REDIS_PREFIX}{drug.brand_name.strip().lower()}"
                drug_json = drug.model_dump_json()
                await self._redis.set(brand_key, drug_json)

                # Store under generic name too, if present and non-empty
                if drug.generic_name and drug.generic_name.strip():
                    generic_normalized = drug.generic_name.strip().lower()
                    brand_normalized = drug.brand_name.strip().lower()
                    if generic_normalized != brand_normalized:
                        generic_key = f"{DRUG_REDIS_PREFIX}{generic_normalized}"
                        await self._redis.set(generic_key, drug_json)

                loaded += 1

        return loaded

    # ── FR-5: load_all() ─────────────────────────────────────────────────────
    async def load_all(self) -> int:
        """Load all drug entries from CSV into Redis. Returns count loaded."""
        count = await self._load_csv()

        if count == 0:
            logger.warning("No valid drug entries loaded from {}", self._csv_path.name)
        else:
            logger.info("Drug CSV loaded: {} entries from {}", count, self._csv_path.name)

        return count


# ── FR-6: load_drug_csv() module-level function ──────────────────────────────
async def load_drug_csv(redis_client) -> int:
    """Convenience wrapper: create DrugCSVLoader and call load_all()."""
    loader = DrugCSVLoader(redis_client)
    return await loader.load_all()


# ══════════════════════════════════════════════════════════════════════════════
# S8.3 — lookup_drug
# ══════════════════════════════════════════════════════════════════════════════

# ── S8.3 FR-4: DRUG_CACHE_TTL_SECONDS constant ──────────────────────────────
DRUG_CACHE_TTL_SECONDS: int = 604800  # 7 days


# ── S8.3 FR-1: _normalize_drug_name() ───────────────────────────────────────

# Common Indian prescription prefixes (Tab., Cap., Inj., Syp., etc.)
_RX_PREFIX_RE = re.compile(
    r"^(?:tab\.?|cap\.?|inj\.?|syp\.?|susp\.?|oint\.?|cr\.?|gel\.?|drop\.?|sachet\.?)\s+",
    re.IGNORECASE,
)
# Trailing dosage pattern (e.g. "500mg", "250 mg", "10ml")
_DOSAGE_SUFFIX_RE = re.compile(
    r"\s+\d+(?:\.\d+)?\s*(?:mg|g|mcg|ml|iu|%)\s*$",
    re.IGNORECASE,
)


def _normalize_drug_name(name: str) -> str:
    """Normalize a drug name for lookup: lowercase, strip Rx prefixes and dosage suffixes."""
    result = re.sub(r"\s+", " ", name.strip()).lower()
    # Strip common prescription prefixes like "tab.", "cap.", "inj."
    result = _RX_PREFIX_RE.sub("", result).strip()
    # Strip trailing dosage like "500mg", "250 mg"
    result = _DOSAGE_SUFFIX_RE.sub("", result).strip()
    return result


# ══════════════════════════════════════════════════════════════════════════════
# S8.5 — IndianMedicineDB API client
# ══════════════════════════════════════════════════════════════════════════════

# ── S8.5 FR-1: API base URL constant ─────────────────────────────────────────
INDIANMEDICINEDB_BASE_URL: str = "https://api.indianmedicinedb.com/v1/medicines"

# ── S8.5 FR-7: httpx timeout ─────────────────────────────────────────────────
_API_TIMEOUT: float = 10.0


def _is_retryable_httpx_error(exc: BaseException) -> bool:
    """Return True for transient errors that should be retried."""
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
        return True
    return False


# ── S8.5 FR-3: response field mapping ────────────────────────────────────────
def _map_api_response_to_drug_info(data: dict) -> DrugInfo:
    """Map IndianMedicineDB API response fields to DrugInfo model."""
    return DrugInfo.model_validate(
        {
            "brand_name": data.get("brand_name"),
            "generic_name": data.get("generic_name"),
            "therapeutic_class": data.get("therapeutic_class"),
            "purpose_en": data.get("purpose"),
            "side_effects_en": data.get("side_effects"),
            "timing_instructions": data.get("timing"),
            "known_interactions": data.get("interactions"),
        }
    )


# ── S8.5 FR-2/FR-4: _call_indianmedicinedb() with retry ─────────────────────
async def _call_indianmedicinedb(
    medicine_name: str,
    request_id: str | None = None,
) -> DrugInfo | None:
    """Look up a medicine via the IndianMedicineDB API.

    Returns DrugInfo on success, None on any failure. Never raises.
    Retries on 5xx, timeout, and connection errors (3 attempts, exp backoff).
    """
    normalized = medicine_name.strip().lower()
    if not normalized:
        return None

    logger.debug(
        "IndianMedicineDB API lookup for '{}' | request_id={}",
        normalized,
        request_id,
    )

    try:
        result = await _call_indianmedicinedb_with_retry(normalized, request_id)
        return result
    except Exception as exc:
        logger.warning(
            "IndianMedicineDB API failed for '{}': {} | request_id={}",
            normalized,
            exc,
            request_id,
        )
        return None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(_is_retryable_httpx_error),
    reraise=True,
)
async def _call_indianmedicinedb_with_retry(
    normalized_name: str,
    request_id: str | None = None,
) -> DrugInfo | None:
    """Inner function with tenacity retry — called by _call_indianmedicinedb."""
    async with httpx.AsyncClient(timeout=_API_TIMEOUT) as client:
        resp = await client.get(
            f"{INDIANMEDICINEDB_BASE_URL}/search",
            params={"name": normalized_name},
        )

        # 404 → not found, no retry
        if resp.status_code == 404:
            logger.debug(
                "IndianMedicineDB 404 for '{}' | request_id={}",
                normalized_name,
                request_id,
            )
            return None

        # 4xx (non-404) → bad request, no retry
        if 400 <= resp.status_code < 500:
            logger.warning(
                "IndianMedicineDB {} for '{}' | request_id={}",
                resp.status_code,
                normalized_name,
                request_id,
            )
            return None

        # 5xx → raise to trigger tenacity retry
        resp.raise_for_status()

        # Parse JSON
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "IndianMedicineDB invalid JSON for '{}': {} | request_id={}",
                normalized_name,
                exc,
                request_id,
            )
            return None

        # Validate into DrugInfo
        try:
            drug = _map_api_response_to_drug_info(data)
        except ValidationError as exc:
            logger.warning(
                "IndianMedicineDB validation error for '{}': {} | request_id={}",
                normalized_name,
                exc,
                request_id,
            )
            return None

        logger.debug(
            "IndianMedicineDB success for '{}' → {} | request_id={}",
            normalized_name,
            drug.brand_name,
            request_id,
        )
        return drug


# ── S8.3 FR-2/FR-3: lookup_drug() ───────────────────────────────────────────
async def lookup_drug(
    redis_client,
    medicine_name: str,
    request_id: str | None = None,
) -> DrugInfo | None:
    """Look up a drug by name: Redis first, then API fallback.

    Returns DrugInfo if found, None otherwise. Never raises.
    """
    normalized = _normalize_drug_name(medicine_name)

    # Empty name → early return
    if not normalized:
        return None

    redis_key = f"{DRUG_REDIS_PREFIX}{normalized}"

    # ── Redis hit path ───────────────────────────────────────────────────
    try:
        cached = await redis_client.get(redis_key)
        if cached is not None:
            try:
                drug = DrugInfo.model_validate_json(cached)
                logger.debug(
                    "Drug cache hit for '{}' | request_id={}",
                    normalized,
                    request_id,
                )
                return drug
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning(
                    "Invalid cached drug data for '{}': {} | request_id={}",
                    normalized,
                    exc,
                    request_id,
                )
        else:
            logger.debug(
                "Drug cache miss for '{}' | request_id={}",
                normalized,
                request_id,
            )
    except Exception as exc:
        logger.warning(
            "Redis error looking up '{}': {} | request_id={}",
            normalized,
            exc,
            request_id,
        )
        return None

    # ── API fallback path ────────────────────────────────────────────────
    try:
        result = await _call_indianmedicinedb(medicine_name, request_id=request_id)
    except Exception as exc:
        logger.warning(
            "API error looking up '{}': {} | request_id={}",
            normalized,
            exc,
            request_id,
        )
        return None

    if result is not None:
        # Cache the API result with TTL
        try:
            await redis_client.set(redis_key, result.model_dump_json(), ex=DRUG_CACHE_TTL_SECONDS)
            logger.debug(
                "Cached API result for '{}' (TTL={}s) | request_id={}",
                normalized,
                DRUG_CACHE_TTL_SECONDS,
                request_id,
            )
        except Exception as exc:
            logger.warning(
                "Failed to cache API result for '{}': {} | request_id={}",
                normalized,
                exc,
                request_id,
            )
        return result

    logger.debug(
        "Drug not found anywhere for '{}' | request_id={}",
        normalized,
        request_id,
    )
    return None


# ══════════════════════════════════════════════════════════════════════════════
# S8.4 — enrich_prescription
# ══════════════════════════════════════════════════════════════════════════════


async def enrich_prescription(
    redis_client,
    prescription: PrescriptionData,
    request_id: str | None = None,
) -> list[DrugInfo | None]:
    """Look up DrugInfo for every medicine in a prescription concurrently.

    Returns a list aligned positionally with ``prescription.medicines``.
    Never raises — individual failures produce ``None`` entries.
    """
    medicines = prescription.medicines

    if not medicines:
        logger.debug("No medicines to enrich | request_id={}", request_id)
        return []

    logger.info(
        "Enriching {} medicines | request_id={}",
        len(medicines),
        request_id,
    )

    try:
        results: list[DrugInfo | None] = list(
            await asyncio.gather(
                *(
                    lookup_drug(redis_client, med.medicine_name, request_id=request_id)
                    for med in medicines
                )
            )
        )
    except Exception as exc:
        logger.warning(
            "Gather failed during enrichment: {} | request_id={}",
            exc,
            request_id,
        )
        results = [None] * len(medicines)

    hits = sum(1 for r in results if r is not None)
    misses = len(results) - hits
    logger.info(
        "Enrichment complete: {} hits, {} misses | request_id={}",
        hits,
        misses,
        request_id,
    )

    return results
