# Spec S8.3 — lookup drug

## Overview
Single-drug lookup function that first checks Redis (populated by S8.2's `load_drug_csv()`), and on cache miss falls back to the IndianMedicineDB API. API results are cached in Redis for 7 days. Returns a `DrugInfo` Pydantic model or `None` if the drug is not found anywhere.

## Dependencies
- **S8.2** — `load_drug_csv()` (populates Redis with `drug:{name}` keys)
- **S2.4** — `DrugInfo` Pydantic model

## Target Location
`backend/app/services/drug_lookup.py`

---

## Functional Requirements

### FR-1: `_normalize_drug_name()` helper
- **What**: Pure function that normalizes a medicine name for Redis key lookup.
- **Inputs**: `name: str` — raw medicine name from extraction.
- **Outputs**: `str` — lowercase, stripped, whitespace-collapsed name.
- **Edge cases**: Empty string returns empty string. Leading/trailing whitespace stripped. Multiple internal spaces collapsed to single space.

### FR-2: `lookup_drug()` — Redis hit path
- **What**: Async function that looks up a drug by name in Redis.
- **Inputs**: `redis_client` (async Redis), `medicine_name: str`, `request_id: str | None = None`.
- **Outputs**: `DrugInfo | None`.
- **Behavior**: Normalize the name → build key `drug:{normalized}` → `redis.get(key)` → if found, parse JSON → validate as `DrugInfo` → return.
- **Edge cases**: Empty name returns `None` immediately. Redis returns `None` → cache miss path.

### FR-3: `lookup_drug()` — API fallback path
- **What**: On Redis cache miss, call the IndianMedicineDB API via `_call_indianmedicinedb()` (stub for S8.5).
- **Inputs**: Same as FR-2.
- **Outputs**: `DrugInfo | None`.
- **Behavior**: Call `_call_indianmedicinedb(medicine_name, request_id)` → if result is not `None`, cache it in Redis with 7-day TTL (`drug:{normalized}` key) → return result.
- **Edge cases**: API returns `None` → return `None` (do not cache misses). API raises exception → log warning, return `None`.

### FR-4: `DRUG_CACHE_TTL_SECONDS` constant
- **What**: Module-level constant for the Redis TTL applied to API-fetched drug results.
- **Value**: `604800` (7 days in seconds).

### FR-5: `_call_indianmedicinedb()` stub
- **What**: Async function placeholder for S8.5 implementation. Returns `None` for now.
- **Inputs**: `medicine_name: str`, `request_id: str | None = None`.
- **Outputs**: `DrugInfo | None` (always `None` in this spec).
- **Notes**: S8.5 will replace the stub body with actual httpx + tenacity logic.

### FR-6: Logging
- **What**: Log all lookup operations with Loguru.
- **Behavior**:
  - Log cache hit at `debug` level with drug name.
  - Log cache miss at `debug` level with drug name.
  - Log API fallback result (found/not found) at `debug` level.
  - Log any errors (Redis, JSON parse, validation) at `warning` level.
  - Include `request_id` in log context when provided.
- **PHI safety**: Never log patient data. Drug names are not PHI.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `lookup_drug("Amoxicillin", redis)` returns `DrugInfo` when `drug:amoxicillin` exists in Redis.
- [ ] **Outcome 2**: `lookup_drug("UnknownDrug", redis)` returns `None` when not in Redis and API stub returns `None`.
- [ ] **Outcome 3**: `_normalize_drug_name("  Paracetamol  500mg  ")` returns `"paracetamol 500mg"`.
- [ ] **Outcome 4**: `DRUG_CACHE_TTL_SECONDS` equals `604800`.
- [ ] **Outcome 5**: API result is cached in Redis with 7-day TTL on successful lookup.
- [ ] **Outcome 6**: Errors in Redis or API do not propagate — function returns `None` gracefully.

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_normalize_drug_name_basic**: Lowercase + strip.
2. **test_normalize_drug_name_whitespace_collapse**: Multiple spaces → single space.
3. **test_normalize_drug_name_empty**: Empty string → empty string.
4. **test_lookup_drug_importable**: Function is importable from module.
5. **test_lookup_drug_is_async**: Function is a coroutine.
6. **test_lookup_drug_signature**: Accepts `redis_client`, `medicine_name`, optional `request_id`.
7. **test_lookup_drug_redis_hit**: Redis GET returns valid JSON → returns `DrugInfo`.
8. **test_lookup_drug_redis_miss_api_miss**: Redis GET returns `None`, API stub returns `None` → returns `None`.
9. **test_lookup_drug_redis_miss_api_hit**: Redis GET returns `None`, mocked API returns `DrugInfo` → caches and returns `DrugInfo`.
10. **test_lookup_drug_cache_ttl_on_api_result**: When API returns result, `redis.set()` called with TTL = 604800.
11. **test_lookup_drug_empty_name**: Empty string → `None` immediately (no Redis call).
12. **test_lookup_drug_redis_error_resilience**: Redis raises exception → returns `None`, does not crash.
13. **test_lookup_drug_api_error_resilience**: API raises exception → returns `None`, does not crash.
14. **test_lookup_drug_invalid_json_in_redis**: Redis returns malformed JSON → returns `None` (falls through to API).
15. **test_lookup_drug_logging_cache_hit**: Cache hit logs at debug level.
16. **test_lookup_drug_logging_cache_miss**: Cache miss logs at debug level.
17. **test_drug_cache_ttl_constant**: `DRUG_CACHE_TTL_SECONDS == 604800`.
18. **test_call_indianmedicinedb_stub**: Stub exists, is async, returns `None`.
19. **test_lookup_drug_normalizes_name**: "  AMOXICILLIN  " looks up `drug:amoxicillin`.
20. **test_lookup_drug_request_id_passed**: `request_id` passed through to API stub.

### Mocking Strategy
- **Redis**: `AsyncMock` for `redis.get()` and `redis.set()`.
- **API stub**: `unittest.mock.patch` on `_call_indianmedicinedb`.
- **Loguru**: Capture logs via `loguru` sink or mock `logger`.

### Coverage Expectation
- All public functions have at least one test; edge cases covered.
- 20 tests total.

---

## References
- roadmap.md (Phase 8 — Drug Lookup)
- `backend/app/services/drug_lookup.py` (S8.2 existing code)
- `backend/app/models/schemas.py` (DrugInfo model)
