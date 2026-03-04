# Spec S8.2 — Load Drug CSV

## Overview
Reads the drug database CSV file (`data/drugs/medicines.csv`) and loads all entries into Redis as hash maps. Each drug is stored under both its normalized brand name and generic name keys, enabling fast O(1) lookups by either name. This function is called by `make seed` at startup or deployment time.

## Dependencies
- **S2.2** — Async Redis client (`backend/app/db/redis.py`)
- **S8.1** — Drug database CSV file (`data/drugs/medicines.csv`)

## Target Location
`backend/app/services/drug_lookup.py`

---

## Functional Requirements

### FR-1: DRUG_CSV_PATH constant
- **What**: Module-level `Path` constant pointing to `data/drugs/medicines.csv` relative to the project root (3 parents up from the service file, same pattern as `GLOSSARY_DIR`)
- **Inputs**: None (computed at import time)
- **Outputs**: `pathlib.Path` pointing to the CSV file
- **Edge cases**: File may not exist at runtime (handled by FR-3)

### FR-2: DRUG_REDIS_PREFIX constant
- **What**: Module-level string constant `"drug:"` used as the prefix for all drug Redis keys
- **Inputs**: None
- **Outputs**: `str` — `"drug:"`
- **Edge cases**: None

### FR-3: DrugCSVLoader class
- **What**: A class that reads the CSV file and loads entries into Redis. Constructor accepts a Redis client and an optional `csv_path` override (defaults to `DRUG_CSV_PATH`). Follows the same pattern as `GlossaryLoader`.
- **Inputs**: `redis_client` (async Redis), `csv_path: Path | None`
- **Outputs**: Instance with `_redis` and `_csv_path` attributes

### FR-4: DrugCSVLoader._load_csv() method
- **What**: Async method that reads the CSV, validates each row against `DrugInfo` schema, normalizes names (lowercase, strip whitespace), and stores entries in Redis
- **Inputs**: None (reads from `self._csv_path`)
- **Outputs**: `int` — count of entries loaded
- **Storage**: For each valid row, store the JSON-serialized `DrugInfo` under:
  - `drug:{brand_name_normalized}` (Redis SET key → JSON string)
  - `drug:{generic_name_normalized}` (Redis SET key → JSON string, if generic_name is present and different from brand)
- **Normalization**: `name.strip().lower()` for both brand and generic names
- **Edge cases**:
  - `FileNotFoundError` raised if CSV path doesn't exist
  - Rows with missing `brand_name` are skipped with a warning log
  - Rows failing `DrugInfo` Pydantic validation are skipped with a warning log
  - Duplicate normalized names: later rows overwrite earlier ones (last-write-wins)
  - Empty generic_name: only brand_name key is stored

### FR-5: DrugCSVLoader.load_all() method
- **What**: Public async method that calls `_load_csv()` and returns the result. Logs summary (total entries loaded, total Redis keys written)
- **Inputs**: None
- **Outputs**: `int` — count of entries loaded
- **Edge cases**: If CSV file doesn't exist, raises `FileNotFoundError`. If no valid rows, returns 0 with a warning

### FR-6: load_drug_csv() module-level function
- **What**: Convenience wrapper — creates `DrugCSVLoader(redis_client)` and calls `load_all()`
- **Inputs**: `redis_client` (async Redis client)
- **Outputs**: `int` — count of entries loaded
- **Signature**: `async def load_drug_csv(redis_client) -> int`

---

## Tangible Outcomes

- [ ] **Outcome 1**: `DRUG_CSV_PATH` resolves to `data/drugs/medicines.csv` relative to project root
- [ ] **Outcome 2**: `DRUG_REDIS_PREFIX` equals `"drug:"`
- [ ] **Outcome 3**: `DrugCSVLoader` reads CSV and stores each row as `DrugInfo` JSON in Redis under `drug:{normalized_brand}` and `drug:{normalized_generic}` keys
- [ ] **Outcome 4**: Normalization lowercases and strips whitespace from drug names
- [ ] **Outcome 5**: Invalid rows are skipped with warning logs (not raised)
- [ ] **Outcome 6**: `load_drug_csv()` is an async convenience wrapper returning the count of loaded entries
- [ ] **Outcome 7**: All Loguru log calls avoid logging patient data (PHI-safe)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

**Constants (pure, no mocking):**
1. **test_drug_csv_path_is_path**: `DRUG_CSV_PATH` is a `pathlib.Path`
2. **test_drug_csv_path_ends_with_medicines_csv**: Path ends with `data/drugs/medicines.csv`
3. **test_drug_redis_prefix_value**: `DRUG_REDIS_PREFIX == "drug:"`
4. **test_drug_redis_prefix_is_string**: Type is `str`

**DrugCSVLoader constructor:**
5. **test_loader_accepts_redis_client**: Constructor stores `_redis` attribute
6. **test_loader_default_csv_path**: Defaults to `DRUG_CSV_PATH` when no override given
7. **test_loader_custom_csv_path**: Accepts and stores custom path override

**_load_csv() method (mocked Redis):**
8. **test_load_csv_reads_valid_file**: Loads a small test CSV, returns correct count
9. **test_load_csv_stores_brand_key**: Calls `redis.set()` with `drug:{brand_normalized}`
10. **test_load_csv_stores_generic_key**: Calls `redis.set()` with `drug:{generic_normalized}`
11. **test_load_csv_normalizes_names**: Uppercase/whitespace in CSV → lowercase/stripped Redis keys
12. **test_load_csv_value_is_druginfo_json**: Stored value deserializes to valid `DrugInfo`
13. **test_load_csv_skips_invalid_row**: Row with missing brand_name is skipped, warning logged
14. **test_load_csv_file_not_found**: Raises `FileNotFoundError` for missing CSV
15. **test_load_csv_empty_generic_only_brand_key**: Row with empty generic_name → only brand key stored
16. **test_load_csv_duplicate_names_last_wins**: Later row overwrites earlier for same normalized name

**load_all() method:**
17. **test_load_all_returns_count**: Delegates to `_load_csv()` and returns its result
18. **test_load_all_logs_summary**: Logs total entries loaded

**load_drug_csv() module function:**
19. **test_load_drug_csv_is_async**: Function is a coroutine function
20. **test_load_drug_csv_delegates_to_loader**: Creates `DrugCSVLoader` and calls `load_all()`

### Mocking Strategy
- Redis client: `AsyncMock` with mocked `set()` method
- CSV file: Create temporary CSV files in `tmp_path` fixture
- No real Redis or file system I/O in tests

### Coverage Expectation
- All public functions and edge cases covered
- 20 tests total
