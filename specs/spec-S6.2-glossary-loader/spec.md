# Spec S6.2 — GlossaryLoader + load_glossary()

## Overview
Provides a `GlossaryLoader` class and a `load_glossary()` function that reads all per-language glossary JSON files from `data/glossary/` and loads them into Redis as hash maps. Each language gets a Redis hash keyed as `glossary:{lang_code}`, where the field is the medical term (lowercased) and the value is the full entry serialized as a JSON string. Called on startup (lifespan) or manually via `make seed`.

## Dependencies
- **S2.2** — Async Redis client (`backend/app/db/redis.py`): provides `get_redis()`, `init_redis()`
- **S6.1** — Glossary data files (`data/glossary/{lang_code}.json`): 6 JSON files (hi, ta, te, kn, bn, mr), 25 entries each

## Target Location
`backend/app/services/glossary.py`

---

## Functional Requirements

### FR-1: GLOSSARY_DIR constant
- **What**: Module-level `Path` constant pointing to the glossary data directory (`data/glossary/`)
- **Value**: Resolved relative to project root, not relative to the module file
- **Validation**: Must be a `pathlib.Path` object

### FR-2: GLOSSARY_REDIS_PREFIX constant
- **What**: Module-level string constant for the Redis hash key prefix
- **Value**: `"glossary:"`
- **Usage**: Redis key = `f"{GLOSSARY_REDIS_PREFIX}{lang_code}"` (e.g. `glossary:hi`)

### FR-3: GlossaryLoader class
- **What**: A class that encapsulates glossary loading logic
- **Constructor**: `GlossaryLoader(redis_client: redis.asyncio.Redis, glossary_dir: Path | None = None)`
  - `redis_client`: async Redis client instance (injected, not imported globally)
  - `glossary_dir`: optional override for the data directory (defaults to `GLOSSARY_DIR`); enables testing with temp directories
- **Attributes**: `self._redis`, `self._glossary_dir`

### FR-4: GlossaryLoader._load_language_file()
- **What**: Read a single JSON file and load its entries into a Redis hash
- **Signature**: `async def _load_language_file(self, lang_code: str) -> int`
- **Inputs**: `lang_code` — e.g. `"hi"`, `"ta"`
- **Behavior**:
  1. Build file path: `self._glossary_dir / f"{lang_code}.json"`
  2. Read and parse JSON (list of `{"term", "explanation", "vernacular"}` objects)
  3. Validate each entry against the `GlossaryEntry` Pydantic model
  4. For each valid entry, call `HSET` on Redis hash `glossary:{lang_code}` with field = `term.lower()` and value = entry JSON string (compact, via `model_dump_json()`)
  5. Log: number of terms loaded for this language
- **Returns**: count of entries loaded
- **Edge cases**:
  - File not found → raise `FileNotFoundError`
  - Invalid JSON → raise `json.JSONDecodeError`
  - Pydantic validation failure on any entry → log warning and skip that entry (don't abort entire language)

### FR-5: GlossaryLoader.load_all()
- **What**: Load all supported language glossary files into Redis
- **Signature**: `async def load_all(self) -> dict[str, int]`
- **Behavior**:
  1. Discover all `*.json` files in `self._glossary_dir`
  2. Extract `lang_code` from filename (stem, e.g. `"hi"` from `"hi.json"`)
  3. Call `_load_language_file()` for each discovered language
  4. Log summary: total languages loaded, total terms loaded
- **Returns**: `dict` mapping `lang_code` → count of entries loaded (e.g. `{"hi": 25, "ta": 25, ...}`)
- **Edge cases**:
  - Empty directory → return empty dict, log warning
  - One file fails → log error for that file, continue loading others (partial success)

### FR-6: load_glossary() module-level function
- **What**: Convenience async function for use in app lifespan or seed scripts
- **Signature**: `async def load_glossary(redis_client: redis.asyncio.Redis) -> dict[str, int]`
- **Behavior**: Creates a `GlossaryLoader(redis_client)` and calls `load_all()`
- **Returns**: Same as `GlossaryLoader.load_all()`

---

## Tangible Outcomes

- [ ] **Outcome 1**: `GLOSSARY_DIR` is a `pathlib.Path` pointing to `data/glossary/`
- [ ] **Outcome 2**: `GLOSSARY_REDIS_PREFIX` equals `"glossary:"`
- [ ] **Outcome 3**: `GlossaryLoader` accepts `redis_client` and optional `glossary_dir`
- [ ] **Outcome 4**: `_load_language_file("hi")` loads 25 entries into Redis hash `glossary:hi` with lowercase term keys
- [ ] **Outcome 5**: `load_all()` discovers and loads all 6 language files, returns `{lang_code: count}` dict
- [ ] **Outcome 6**: Invalid entries are skipped with a warning, not aborting the entire file
- [ ] **Outcome 7**: Missing files log an error but don't crash the entire load process
- [ ] **Outcome 8**: `load_glossary(redis_client)` is a one-call convenience wrapper
- [ ] **Outcome 9**: All Redis hash values are valid JSON strings parseable back into `GlossaryEntry`

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

**Constants & imports (pure, no mocking):**
1. **test_glossary_module_importable**: `from backend.app.services.glossary import ...` succeeds
2. **test_glossary_dir_is_path**: `GLOSSARY_DIR` is a `pathlib.Path` instance
3. **test_glossary_dir_points_to_data_glossary**: path ends with `data/glossary`
4. **test_glossary_redis_prefix_value**: `GLOSSARY_REDIS_PREFIX == "glossary:"`
5. **test_glossary_loader_class_exists**: `GlossaryLoader` is a class
6. **test_load_glossary_function_exists**: `load_glossary` is an async callable

**GlossaryLoader constructor:**
7. **test_loader_accepts_redis_client**: constructor takes `redis_client` param
8. **test_loader_accepts_optional_glossary_dir**: constructor takes optional `glossary_dir`
9. **test_loader_defaults_to_glossary_dir**: when `glossary_dir` not provided, uses `GLOSSARY_DIR`

**_load_language_file (mocked Redis):**
10. **test_load_language_file_calls_hset**: loads entries into correct Redis hash key
11. **test_load_language_file_lowercase_keys**: term keys are lowercased in Redis
12. **test_load_language_file_values_are_json**: values stored are valid JSON strings
13. **test_load_language_file_returns_count**: returns number of entries loaded
14. **test_load_language_file_file_not_found**: raises `FileNotFoundError` for missing file
15. **test_load_language_file_invalid_json**: raises error for malformed JSON
16. **test_load_language_file_skips_invalid_entry**: invalid Pydantic entries skipped with warning, valid ones loaded

**load_all (mocked Redis + temp directory):**
17. **test_load_all_discovers_json_files**: finds all .json files in directory
18. **test_load_all_returns_lang_count_dict**: returns `{lang_code: count}` mapping
19. **test_load_all_empty_directory**: returns empty dict for empty directory
20. **test_load_all_partial_failure**: one bad file doesn't stop others from loading
21. **test_load_all_logs_summary**: logs total languages and terms loaded

**load_glossary convenience function (mocked Redis):**
22. **test_load_glossary_delegates_to_loader**: creates GlossaryLoader and calls load_all
23. **test_load_glossary_returns_dict**: returns the same dict as load_all

**Integration-style (temp files + mock Redis):**
24. **test_roundtrip_entry_is_valid_glossary_entry**: stored JSON can be parsed back into GlossaryEntry
25. **test_load_real_glossary_files**: loads actual `data/glossary/` files (if present) into mock Redis, verifies counts match

### Mocking Strategy
- **Redis**: Use `AsyncMock` for `redis.asyncio.Redis` — mock `hset` calls, capture arguments
- **Filesystem**: Use `tmp_path` fixture for temp directory tests; use real `data/glossary/` for integration-style tests
- **No external services**: Everything is local (file I/O + Redis)

### Coverage Expectation
- All public functions and class methods have at least one test
- Edge cases (missing files, invalid JSON, invalid entries, empty dirs) are covered
- 25 tests total

---

## References
- roadmap.md — Phase 6, S6.2
- `backend/app/models/schemas.py` — `GlossaryEntry` model (term, explanation, vernacular)
- `backend/app/db/redis.py` — async Redis client with `decode_responses=True`
- `data/glossary/{hi,ta,te,kn,bn,mr}.json` — 6 files, 25 entries each
