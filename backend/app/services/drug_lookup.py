"""Drug lookup service — CSV (S8.2) + lookup (S8.3) + enrichment (S8.4) + API (S8.5).

S8.2: Reads the drug database CSV and loads entries into Redis.
S8.3: lookup_drug() checks Redis first, falls back to IndianMedicineDB API.
       Tiered lookup: brand/generic → salt/composition → therapeutic class → API.
S8.4: enrich_prescription() runs concurrent lookups for all medicines in a prescription.
S8.5: _call_indianmedicinedb() — httpx async GET with tenacity retry.
"""

from __future__ import annotations

import asyncio
import csv
import difflib
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
MEDICINE_DATA_CSV_PATH: Path = (
    Path(__file__).resolve().parents[3] / "data" / "drugs" / "medicine_data.csv"
)

# ── FR-2: DRUG_REDIS_PREFIX constant ──────────────────────────────────────────
DRUG_REDIS_PREFIX: str = "drug:"
SALT_REDIS_PREFIX: str = "salt:"
CATEGORY_REDIS_PREFIX: str = "category:"

# ── In-memory brand name cache for fuzzy matching (L2) ────────────────────────
_brand_name_cache: set[str] = set()
FUZZY_MATCH_CUTOFF: float = 0.8  # difflib similarity threshold
FUZZY_MATCH_MAX_RESULTS: int = 1


def _fuzzy_match_drug_name(name: str) -> str | None:
    """Find the closest brand name match using sequence matching.

    Returns the best match if similarity >= FUZZY_MATCH_CUTOFF, else None.
    Uses stdlib difflib — no extra dependencies, runs in <5ms for 17K names.
    """
    if not _brand_name_cache or not name:
        return None
    matches = difflib.get_close_matches(
        name,
        _brand_name_cache,
        n=FUZZY_MATCH_MAX_RESULTS,
        cutoff=FUZZY_MATCH_CUTOFF,
    )
    if matches:
        logger.debug("Fuzzy match: '{}' → '{}'", name, matches[0])
        return matches[0]
    return None


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

                brand_normalized = drug.brand_name.strip().lower()
                brand_key = f"{DRUG_REDIS_PREFIX}{brand_normalized}"
                drug_json = drug.model_dump_json()
                await self._redis.set(brand_key, drug_json)

                # Populate in-memory cache for fuzzy matching
                _brand_name_cache.add(brand_normalized)

                # Store under generic name too, if present and non-empty
                if drug.generic_name and drug.generic_name.strip():
                    generic_normalized = drug.generic_name.strip().lower()
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
# Salt/Composition + Category Indexing (from medicine_data.csv)
# ══════════════════════════════════════════════════════════════════════════════

# Regex to strip dosage from individual salt components
# e.g. "Paracetamol (500mg)" → "paracetamol", "Amoxycillin (250mg)" → "amoxycillin"
_SALT_DOSAGE_RE = re.compile(r"\s*\(.*?\)\s*$")


def _normalize_salt(salt: str) -> str:
    """Normalize a salt component: lowercase, strip dosage in parens, collapse whitespace."""
    result = _SALT_DOSAGE_RE.sub("", salt)
    result = re.sub(r"\s+", " ", result.strip()).lower()
    return result


def _extract_salt_components(composition: str) -> list[str]:
    """Split a salt_composition string into individual normalized components.

    Input:  "Paracetamol (500mg) + Caffeine (65mg)"
    Output: ["paracetamol", "caffeine"]
    Also returns the full normalized composition as a component.
    """
    if not composition or not composition.strip():
        return []
    parts = [_normalize_salt(p) for p in composition.split("+")]
    parts = [p for p in parts if p and len(p) >= 2]
    # Also add the full composition (without dosages) as a combined key
    full = _normalize_salt(composition.replace("+", " + "))
    if full and full not in parts:
        parts.append(full)
    return parts


def _summarize_for_salt(desc: str) -> str:
    """Extract first 1-2 sentences from medicine_desc, cap at 200 chars."""
    if not desc:
        return ""
    sentences = re.split(r"(?<=[.!])\s+", desc.strip())
    summary_parts: list[str] = []
    char_count = 0
    for s in sentences:
        if char_count + len(s) > 195 and summary_parts:
            break
        summary_parts.append(s)
        char_count += len(s)
        if len(summary_parts) >= 2:
            break
    result = " ".join(summary_parts)
    if len(result) > 200:
        result = result[:197] + "..."
    return result


def _parse_interactions_json(raw: str) -> str:
    """Parse JSON drug_interactions into readable text.

    Input:  {"drug": ["Benazepril", ...], "effect": ["MODERATE", ...]}
    Output: "Benazepril (MODERATE); Captopril (MODERATE)"
    """
    if not raw:
        return ""
    try:
        data = json.loads(raw)
        drugs = data.get("drug", [])
        effects = data.get("effect", [])
        if not drugs:
            return ""
        parts = []
        for i, drug in enumerate(drugs):
            drug = drug.strip()
            if not drug:
                continue
            effect = effects[i].strip() if i < len(effects) else ""
            parts.append(f"{drug} ({effect})" if effect else drug)
        return "; ".join(parts) if parts else ""
    except (json.JSONDecodeError, KeyError, IndexError):
        return ""


class MedicineDataLoader:
    """Reads medicine_data.csv and builds salt/composition + category indexes in Redis.

    This enables tiered lookup:
    - Level 2: salt:{component} → DrugInfo for that salt (same composition = same medical info)
    - Level 3: category:{sub_category} → representative DrugInfo for the category
    """

    def __init__(self, redis_client, csv_path: Path | None = None) -> None:
        self._redis = redis_client
        self._csv_path = csv_path if csv_path is not None else MEDICINE_DATA_CSV_PATH

    async def load_all(self) -> dict[str, int]:
        """Load salt and category indexes from medicine_data.csv.

        Returns dict with counts: {"salts": N, "categories": N, "rows_processed": N}.
        """
        if not self._csv_path.exists():
            logger.warning("medicine_data.csv not found at {}, skipping", self._csv_path)
            return {"salts": 0, "categories": 0, "rows_processed": 0}

        salt_count = 0
        category_count = 0
        rows = 0
        seen_salts: set[str] = set()
        seen_categories: set[str] = set()

        with self._csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows += 1
                name = (row.get("product_name") or "").strip()
                if not name:
                    continue

                composition = (row.get("salt_composition") or "").strip()
                sub_category = (row.get("sub_category") or "").strip().lower()
                desc = (row.get("medicine_desc") or "").strip()
                side_effects = (row.get("side_effects") or "").strip()
                interactions_raw = (row.get("drug_interactions") or "").strip()

                purpose = _summarize_for_salt(desc)
                interactions = _parse_interactions_json(interactions_raw)

                drug_info = DrugInfo(
                    brand_name=name,
                    generic_name=composition,
                    therapeutic_class=sub_category,
                    purpose_en=purpose,
                    side_effects_en=side_effects,
                    timing_instructions="",
                    known_interactions=interactions,
                )
                drug_json = drug_info.model_dump_json()

                # Index by salt components (first-seen per salt wins)
                if composition:
                    components = _extract_salt_components(composition)
                    for comp in components:
                        if comp not in seen_salts:
                            salt_key = f"{SALT_REDIS_PREFIX}{comp}"
                            await self._redis.set(salt_key, drug_json)
                            seen_salts.add(comp)
                            salt_count += 1

                # Index by category (first-seen per category wins)
                if sub_category and sub_category not in seen_categories:
                    cat_key = f"{CATEGORY_REDIS_PREFIX}{sub_category}"
                    await self._redis.set(cat_key, drug_json)
                    seen_categories.add(sub_category)
                    category_count += 1

        logger.info(
            "MedicineData loaded: {} salt indexes, {} category indexes from {} rows",
            salt_count,
            category_count,
            rows,
        )
        return {"salts": salt_count, "categories": category_count, "rows_processed": rows}


async def load_medicine_data(redis_client) -> dict[str, int]:
    """Convenience wrapper: create MedicineDataLoader and call load_all()."""
    loader = MedicineDataLoader(redis_client)
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


# ── Helper: try a single Redis key and return DrugInfo or None ────────────────
async def _try_redis_key(
    redis_client,
    key: str,
    label: str,
    request_id: str | None = None,
) -> DrugInfo | None:
    """Attempt to read and parse a DrugInfo from a single Redis key.

    Returns DrugInfo on hit, None on miss or error. Never raises.
    """
    try:
        cached = await redis_client.get(key)
        if cached is not None:
            try:
                drug = DrugInfo.model_validate_json(cached)
                logger.debug(
                    "{} hit for '{}' | request_id={}",
                    label,
                    key,
                    request_id,
                )
                return drug
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning(
                    "Invalid cached data for '{}': {} | request_id={}",
                    key,
                    exc,
                    request_id,
                )
    except Exception as exc:
        logger.warning(
            "Redis error for '{}': {} | request_id={}",
            key,
            exc,
            request_id,
        )
    return None


# ── S8.3 FR-2/FR-3: lookup_drug() — tiered lookup ───────────────────────────
async def lookup_drug(
    redis_client,
    medicine_name: str,
    request_id: str | None = None,
) -> DrugInfo | None:
    """Look up a drug by name using tiered matching strategy.

    Level 1: Brand/generic name match (drug:{name})
    Level 2: Fuzzy brand name match  (edit distance ≤ threshold)
    Level 3: Salt/composition match  (salt:{name})
    Level 4: Therapeutic class match (category:{name})
    Level 5: IndianMedicineDB API fallback

    Returns DrugInfo if found, None otherwise. Never raises.
    """
    normalized = _normalize_drug_name(medicine_name)

    # Empty name → early return
    if not normalized:
        return None

    # ── Level 1: Brand/generic match ─────────────────────────────────────
    drug_key = f"{DRUG_REDIS_PREFIX}{normalized}"
    result = await _try_redis_key(redis_client, drug_key, "Drug cache", request_id)
    if result is not None:
        return result

    logger.debug(
        "Drug cache miss for '{}' | request_id={}",
        normalized,
        request_id,
    )

    # ── Level 2: Fuzzy brand name match ──────────────────────────────────
    fuzzy_name = _fuzzy_match_drug_name(normalized)
    if fuzzy_name:
        fuzzy_key = f"{DRUG_REDIS_PREFIX}{fuzzy_name}"
        result = await _try_redis_key(redis_client, fuzzy_key, "Fuzzy match", request_id)
        if result is not None:
            return result

    # ── Level 3: Salt/composition match ──────────────────────────────────
    salt_key = f"{SALT_REDIS_PREFIX}{normalized}"
    result = await _try_redis_key(redis_client, salt_key, "Salt match", request_id)
    if result is not None:
        return result

    # ── Level 4: Category match (therapeutic class) ──────────────────────
    cat_key = f"{CATEGORY_REDIS_PREFIX}{normalized}"
    result = await _try_redis_key(redis_client, cat_key, "Category match", request_id)
    if result is not None:
        return result

    # ── Level 5: API fallback ────────────────────────────────────────────
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
        # Cache the API result with TTL under drug: prefix
        try:
            await redis_client.set(drug_key, result.model_dump_json(), ex=DRUG_CACHE_TTL_SECONDS)
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

    # L4: Flag unverified medicine names on the prescription object
    for i, (med, drug) in enumerate(zip(medicines, results)):
        if drug is None:
            med.name_verified = False

    logger.info(
        "Enrichment complete: {} hits, {} misses | request_id={}",
        hits,
        misses,
        request_id,
    )

    return results
