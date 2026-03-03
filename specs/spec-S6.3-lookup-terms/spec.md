# Spec S6.3 — lookup_terms()

## Overview
Given a set of medical terms (extracted from a `PrescriptionData` object) and a `language_code`, performs a batch Redis HGET against the `glossary:{lang_code}` hash and returns a list of matching `GlossaryEntry` objects. This is the runtime lookup path used during the translation pipeline to inject glossary context into the Claude prompt.

## Dependencies
- **S6.2** — GlossaryLoader + `load_glossary()` (`backend/app/services/glossary.py`): provides the `GLOSSARY_REDIS_PREFIX` constant and populated Redis hashes
- **S2.4** — Pydantic models (`backend/app/models/schemas.py`): provides `GlossaryEntry` model

## Target Location
`backend/app/services/glossary.py`

---

## Functional Requirements

### FR-1: `lookup_terms()` function signature
- **What**: Async function that looks up medical terms in the Redis glossary hash for a given language
- **Signature**: `async def lookup_terms(terms: list[str], language_code: str, redis_client: redis.asyncio.Redis) -> list[GlossaryEntry]`
- **Inputs**:
  - `terms`: list of medical term strings (e.g. `["hypertension", "Paracetamol", "twice daily"]`)
  - `language_code`: ISO language code (e.g. `"hi"`, `"ta"`)
  - `redis_client`: async Redis client instance (injected, not imported globally)
- **Outputs**: list of `GlossaryEntry` objects for terms that were found in Redis
- **Edge cases**:
  - Empty `terms` list → return empty list immediately (no Redis calls)
  - No matches found → return empty list
  - `language_code` has no glossary hash in Redis → return empty list (no error)

### FR-2: Term normalization
- **What**: Terms are normalized to lowercase before Redis lookup to match the storage format from S6.2
- **Behavior**: Each term in `terms` is `.strip().lower()` before use as a Redis HGET field
- **Edge cases**:
  - Whitespace-only terms → skip (do not query Redis with empty string)
  - Duplicate terms after normalization → deduplicate before querying (avoid redundant Redis calls)

### FR-3: Batch Redis HGET
- **What**: Use Redis `HMGET` (single round-trip) instead of N individual `HGET` calls for efficiency
- **Redis key**: `f"{GLOSSARY_REDIS_PREFIX}{language_code}"` (e.g. `glossary:hi`)
- **Redis fields**: list of normalized term strings
- **Behavior**: Single `HMGET` call returns a list of values (JSON strings or `None` for misses)
- **Parse**: Each non-None value is parsed via `json.loads()` and validated as a `GlossaryEntry`

### FR-4: Error resilience
- **What**: Lookup failures should not crash the pipeline — graceful degradation
- **Behavior**:
  - Redis connection error → log warning with `request_id` context, return empty list
  - JSON parse error on a single entry → log warning, skip that entry, continue with others
  - Pydantic validation error on a single entry → log warning, skip that entry, continue with others
- **Logging**: Use Loguru; include `language_code` and term count in log messages

### FR-5: Return ordering
- **What**: Returned `GlossaryEntry` objects maintain the order of the input `terms` list (excluding misses and invalid entries)
- **Rationale**: Consistent ordering makes it easier for the translation prompt to align glossary context with prescription data

---

## Tangible Outcomes

- [ ] **Outcome 1**: `lookup_terms` is importable from `backend.app.services.glossary`
- [ ] **Outcome 2**: `lookup_terms` is an async function accepting `(terms, language_code, redis_client)`
- [ ] **Outcome 3**: Empty terms list returns `[]` without any Redis calls
- [ ] **Outcome 4**: Terms are normalized to lowercase and stripped before lookup
- [ ] **Outcome 5**: Duplicate terms (after normalization) are deduplicated before querying
- [ ] **Outcome 6**: Uses `HMGET` for a single Redis round-trip (not N separate `HGET` calls)
- [ ] **Outcome 7**: Matching entries are returned as valid `GlossaryEntry` objects
- [ ] **Outcome 8**: Non-matching terms are silently excluded (no error)
- [ ] **Outcome 9**: Redis errors return empty list with a logged warning
- [ ] **Outcome 10**: Invalid JSON or Pydantic errors on individual entries skip that entry, not all entries

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

**Imports & signature (pure, no mocking):**
1. **test_lookup_terms_importable**: `from backend.app.services.glossary import lookup_terms` succeeds
2. **test_lookup_terms_is_async**: `lookup_terms` is a coroutine function
3. **test_lookup_terms_signature**: accepts `terms`, `language_code`, `redis_client` params

**Empty / no-op cases (mocked Redis):**
4. **test_empty_terms_returns_empty_list**: `lookup_terms([], "hi", redis)` returns `[]`
5. **test_empty_terms_no_redis_call**: Redis `hmget` is NOT called when terms list is empty
6. **test_whitespace_only_terms_skipped**: terms like `["  ", ""]` are skipped, returns `[]`

**Term normalization (mocked Redis):**
7. **test_terms_lowercased**: `"Hypertension"` becomes `"hypertension"` in Redis query
8. **test_terms_stripped**: `"  fever  "` becomes `"fever"` in Redis query
9. **test_duplicate_terms_deduplicated**: `["fever", "Fever", "FEVER"]` results in single `"fever"` query

**Redis interaction (mocked Redis):**
10. **test_uses_hmget_not_hget**: verifies `hmget` is called (batch), not `hget`
11. **test_correct_redis_key**: Redis key is `glossary:{language_code}`
12. **test_hmget_called_with_normalized_terms**: the fields passed to `hmget` are normalized

**Happy path (mocked Redis returning valid JSON):**
13. **test_returns_glossary_entries**: matching terms return valid `GlossaryEntry` objects
14. **test_multiple_matches**: multiple terms found returns multiple entries
15. **test_partial_matches**: some terms found, some not — only found ones returned
16. **test_no_matches_returns_empty**: all terms miss → returns `[]`
17. **test_return_order_matches_input**: entries returned in same order as input terms

**Error resilience (mocked Redis):**
18. **test_redis_error_returns_empty_list**: Redis exception → returns `[]`, logs warning
19. **test_invalid_json_entry_skipped**: one entry has bad JSON → skipped, others returned
20. **test_invalid_pydantic_entry_skipped**: one entry fails `GlossaryEntry` validation → skipped, others returned

### Mocking Strategy
- **Redis**: Use `AsyncMock` for `redis.asyncio.Redis` — mock `hmget` to return controlled values
- **No external services**: Everything is Redis + JSON parsing
- **Loguru**: Capture logs with `loguru` sink or `caplog` fixture to verify warning messages

### Coverage Expectation
- All public functions have at least one test; edge cases covered
- 20 tests total
- All paths through `lookup_terms` exercised: empty input, normalization, dedup, happy path, partial match, errors

---

## References
- roadmap.md — Phase 6, S6.3
- `backend/app/models/schemas.py` — `GlossaryEntry` model (term, explanation, vernacular)
- `backend/app/services/glossary.py` — `GLOSSARY_REDIS_PREFIX` from S6.2
- `backend/app/db/redis.py` — async Redis client with `decode_responses=True`
