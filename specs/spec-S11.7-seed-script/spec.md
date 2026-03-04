# Spec S11.7 — Seed Script

## Overview
A standalone async Python script (`backend/scripts/seed.py`) that loads the drug database CSV into Redis and loads all glossary JSON files into Redis. Invoked via `make seed` (Docker) or directly via `python backend/scripts/seed.py` (local). Reuses the existing `load_drug_csv()` from S8.2 and `load_glossary()` from S6.2 — no data-loading logic is duplicated. The script connects to Redis using the app's config, runs both loaders, logs summary counts, and exits with appropriate exit codes.

## Dependencies
- S8.2 (`load_drug_csv()` in `backend/app/services/drug_lookup.py`)
- S6.2 (`load_glossary()` in `backend/app/services/glossary.py`)
- S2.5 (Alembic migrations — seed assumes DB/Redis are available)
- S1.3 (pydantic-settings config — REDIS_URL from `.env`)

## Target Location
- `backend/scripts/seed.py` — the seed script
- `backend/scripts/__init__.py` — package init (for `python -m scripts.seed`)
- `Makefile` — `seed` target already exists (`docker compose exec app python -m scripts.seed`)

---

## Functional Requirements

### FR-1: Script entry point
- **What**: `backend/scripts/seed.py` must be runnable as `python backend/scripts/seed.py` (local) and `python -m scripts.seed` (Docker). Uses `asyncio.run()` with a `main()` async function.
- **Inputs**: None (reads REDIS_URL from environment via `settings`)
- **Outputs**: Logs summary to stdout via Loguru, exits with code 0 on success, 1 on failure
- **Edge cases**: Redis not reachable → log error, exit 1

### FR-2: Redis connection management
- **What**: Script creates its own async Redis connection using `redis.asyncio.from_url(settings.REDIS_URL)`, runs the loaders, and closes the connection when done (even on error).
- **Inputs**: `settings.REDIS_URL`
- **Outputs**: A connected Redis client passed to both loaders
- **Edge cases**: Connection failure → caught, logged, exit 1

### FR-3: Load drug CSV into Redis
- **What**: Call `load_drug_csv(redis_client)` from `backend.app.services.drug_lookup`. Log the count of drugs loaded.
- **Inputs**: Redis client
- **Outputs**: Integer count of drugs loaded
- **Edge cases**: CSV missing or malformed → `load_drug_csv` raises, script catches and logs

### FR-4: Load glossary files into Redis
- **What**: Call `load_glossary(redis_client)` from `backend.app.services.glossary`. Log per-language counts.
- **Inputs**: Redis client
- **Outputs**: Dict of `{lang_code: count}` entries loaded
- **Edge cases**: Missing JSON files → `load_glossary` raises, script catches and logs

### FR-5: Summary logging
- **What**: After both loaders complete, log a summary: total drugs loaded, total glossary terms loaded (per language and grand total), total elapsed time.
- **Inputs**: Results from FR-3 and FR-4
- **Outputs**: Loguru info messages
- **Edge cases**: Partial failure (drugs loaded but glossary failed) → log what succeeded, still exit 1

### FR-6: Idempotent execution
- **What**: Running the script multiple times must be safe. Redis hash SET operations overwrite existing keys, so re-seeding replaces stale data without duplicates.
- **Inputs**: Same data files
- **Outputs**: Same Redis state regardless of how many times run
- **Edge cases**: N/A (Redis HSET is naturally idempotent)

### FR-7: Local seed Makefile target
- **What**: Add a `local-seed` target to the Makefile that runs the seed script without Docker: `cd backend && python -m scripts.seed`
- **Inputs**: N/A
- **Outputs**: Seed script runs locally using .env settings
- **Edge cases**: N/A

---

## Tangible Outcomes

- [ ] **Outcome 1**: `backend/scripts/seed.py` exists and is importable
- [ ] **Outcome 2**: `backend/scripts/__init__.py` exists (package marker)
- [ ] **Outcome 3**: Running `python -m scripts.seed` (from backend/) with a mock Redis loads drugs + glossary
- [ ] **Outcome 4**: Script logs drug count and per-language glossary counts
- [ ] **Outcome 5**: Script exits 0 on success, 1 on any failure
- [ ] **Outcome 6**: Script closes Redis connection on success and failure
- [ ] **Outcome 7**: `make local-seed` target exists in Makefile
- [ ] **Outcome 8**: Existing `make seed` (Docker) target is compatible with the script path
- [ ] **Outcome 9**: Re-running the script is idempotent (no duplicate keys)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
Test file: `backend/tests/test_s11_7_seed_script.py`

1. **test_seed_module_importable**: `backend.scripts.seed` can be imported
2. **test_seed_has_main_function**: `main()` is an async function
3. **test_seed_init_exists**: `backend/scripts/__init__.py` exists
4. **test_seed_connects_to_redis**: `main()` creates a Redis connection from settings.REDIS_URL
5. **test_seed_calls_load_drug_csv**: `main()` calls `load_drug_csv(redis_client)`
6. **test_seed_calls_load_glossary**: `main()` calls `load_glossary(redis_client)`
7. **test_seed_logs_drug_count**: After `load_drug_csv`, logs the count
8. **test_seed_logs_glossary_counts**: After `load_glossary`, logs per-language counts
9. **test_seed_logs_total_summary**: Logs a total summary line
10. **test_seed_logs_elapsed_time**: Summary includes elapsed time
11. **test_seed_closes_redis_on_success**: Redis `.aclose()` called after successful run
12. **test_seed_closes_redis_on_failure**: Redis `.aclose()` called even when a loader fails
13. **test_seed_exits_zero_on_success**: Returns/exits 0 when both loaders succeed
14. **test_seed_exits_one_on_drug_failure**: Returns/exits 1 when `load_drug_csv` raises
15. **test_seed_exits_one_on_glossary_failure**: Returns/exits 1 when `load_glossary` raises
16. **test_seed_exits_one_on_redis_connection_failure**: Returns/exits 1 when Redis connection fails
17. **test_seed_partial_failure_logs_success**: If drugs succeed but glossary fails, drug count is still logged
18. **test_seed_calls_loaders_in_order**: Drugs loaded before glossary (or both called)
19. **test_makefile_local_seed_target**: Makefile has `local-seed` target
20. **test_makefile_seed_target_compatible**: Existing `seed` target uses `python -m scripts.seed`

### Mocking Strategy
- Mock `redis.asyncio.from_url` to return an `AsyncMock` Redis client
- Mock `load_drug_csv` and `load_glossary` (patch at their import locations)
- Mock `settings.REDIS_URL` via environment variable or patch
- Mock `sys.exit` to capture exit codes (or test return values)

### Coverage Expectation
- All public functions have at least one test; edge cases covered
- 20 tests total

---

## References
- roadmap.md — S11.7 entry
- `backend/app/services/drug_lookup.py` — `load_drug_csv(redis_client) -> int`
- `backend/app/services/glossary.py` — `load_glossary(redis_client) -> dict[str, int]`
- `backend/app/core/config.py` — `settings.REDIS_URL`
- `Makefile` — existing `seed` target
