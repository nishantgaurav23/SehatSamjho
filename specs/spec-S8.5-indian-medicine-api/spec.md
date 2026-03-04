# Spec S8.5 — IndianMedicineDB API client

## Overview
Replace the `_call_indianmedicinedb()` stub in `drug_lookup.py` with a real implementation. Makes an httpx async GET request to the IndianMedicineDB API to look up medicine information. Parses the JSON response into a `DrugInfo` Pydantic model. Uses Tenacity retry (3 attempts, exponential backoff) for transient HTTP errors. Returns `DrugInfo` on success, `None` on 404/timeout/parse failure. This serves as the fallback path when a drug is not found in the local Redis cache.

## Dependencies
- S8.3 (`lookup_drug()` — calls `_call_indianmedicinedb()` on cache miss)

## Target Location
`backend/app/services/drug_lookup.py`

---

## Functional Requirements

### FR-1: API base URL constant
- **What**: `INDIANMEDICINEDB_BASE_URL` module-level constant
- **Value**: `"https://api.indianmedicinedb.com/v1/medicines"` (configurable for testing)
- **Edge cases**: No trailing slash

### FR-2: `_call_indianmedicinedb()` implementation
- **What**: Replace the stub with a real async function that calls the API
- **Signature**: `async def _call_indianmedicinedb(medicine_name: str, request_id: str | None = None) -> DrugInfo | None`
- **Behavior**:
  1. Normalize medicine name (strip, lowercase)
  2. Make httpx async GET to `{base_url}/search?name={medicine_name}`
  3. Parse JSON response
  4. Validate into `DrugInfo`
  5. Return `DrugInfo` or `None`
- **Edge cases**: Empty name returns `None` immediately

### FR-3: Response parsing
- **What**: Map API JSON response fields to `DrugInfo` fields
- **Expected API response shape**: `{"brand_name": "...", "generic_name": "...", "therapeutic_class": "...", "purpose": "...", "side_effects": "...", "timing": "...", "interactions": "..."}`
- **Mapping**: `purpose` → `purpose_en`, `side_effects` → `side_effects_en`, `timing` → `timing_instructions`, `interactions` → `known_interactions`
- **Edge cases**: Missing fields → `None` (DrugInfo allows optional fields). Completely invalid JSON → return `None`

### FR-4: Tenacity retry
- **What**: Wrap the httpx call with `@retry` decorator
- **Config**: 3 attempts, exponential backoff (wait_exponential: multiplier=1, min=1, max=10)
- **Retry on**: `httpx.HTTPStatusError` (5xx only), `httpx.TimeoutException`, `httpx.ConnectError`
- **Do NOT retry on**: 404 (not found), 400 (bad request), validation errors
- **Edge cases**: After max retries, return `None` (never raise to caller)

### FR-5: Error handling
- **What**: Handle all failure modes gracefully
- **404**: Log debug, return `None`
- **4xx (non-404)**: Log warning, return `None`
- **5xx after retries**: Log warning with request_id, return `None`
- **Timeout**: Log warning, return `None`
- **JSON parse error**: Log warning, return `None`
- **Pydantic validation error**: Log warning, return `None`
- **Never raises** — always returns `DrugInfo | None`

### FR-6: Logging
- **What**: Log API call start, success, and all failure modes with request_id
- **Inputs**: request_id passed through
- **Outputs**: Loguru debug/warning messages

### FR-7: httpx client management
- **What**: Use `httpx.AsyncClient` with a reasonable timeout (10 seconds)
- **Behavior**: Create a fresh client per call (no persistent connection pool needed for prototype)
- **Edge cases**: Client cleanup via `async with`

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_call_indianmedicinedb` is defined (not a stub) in `drug_lookup.py`
- [ ] **Outcome 2**: `INDIANMEDICINEDB_BASE_URL` constant exists
- [ ] **Outcome 3**: Uses `httpx.AsyncClient` for async HTTP GET
- [ ] **Outcome 4**: Tenacity retry with 3 attempts on transient errors
- [ ] **Outcome 5**: Returns `None` on 404/timeout/parse-error (never raises)
- [ ] **Outcome 6**: Logs include request_id for all outcomes
- [ ] **Outcome 7**: Maps API response fields to DrugInfo correctly

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_indianmedicinedb_base_url_constant**: Constant exists and is a string URL
2. **test_call_indianmedicinedb_is_async**: Verify it's a coroutine function
3. **test_call_indianmedicinedb_signature**: Accepts medicine_name, request_id params
4. **test_call_indianmedicinedb_empty_name**: Empty string returns None
5. **test_call_indianmedicinedb_success**: Mock 200 response → returns DrugInfo
6. **test_call_indianmedicinedb_field_mapping**: API fields mapped to DrugInfo fields correctly
7. **test_call_indianmedicinedb_partial_response**: Missing optional fields → DrugInfo with Nones
8. **test_call_indianmedicinedb_404_returns_none**: Mock 404 → returns None
9. **test_call_indianmedicinedb_400_returns_none**: Mock 400 → returns None
10. **test_call_indianmedicinedb_500_after_retries**: Mock 500 → retries exhausted → returns None
11. **test_call_indianmedicinedb_timeout_returns_none**: Mock timeout → returns None
12. **test_call_indianmedicinedb_connect_error_returns_none**: Mock connection error → returns None
13. **test_call_indianmedicinedb_invalid_json_returns_none**: Mock non-JSON body → returns None
14. **test_call_indianmedicinedb_validation_error_returns_none**: JSON missing brand_name → returns None
15. **test_call_indianmedicinedb_retry_on_5xx**: Mock 500 then 200 → retries and succeeds
16. **test_call_indianmedicinedb_no_retry_on_404**: Mock 404 → no retry (called once)
17. **test_call_indianmedicinedb_logs_request_id**: request_id appears in log messages
18. **test_call_indianmedicinedb_logs_success**: Logs debug on successful lookup
19. **test_call_indianmedicinedb_logs_not_found**: Logs debug on 404
20. **test_call_indianmedicinedb_uses_httpx**: Verifies httpx.AsyncClient is used

### Mocking Strategy
- Mock `httpx.AsyncClient` responses (use `unittest.mock.AsyncMock` or `respx` library)
- Mock at `backend.app.services.drug_lookup.httpx.AsyncClient` to control HTTP responses
- No real HTTP calls — all network mocked

### Coverage Expectation
- All branches covered: success, 404, 4xx, 5xx+retry, timeout, parse error, validation error
- 20 tests total

---

## References
- roadmap.md (S8.5 row)
- `backend/app/services/drug_lookup.py` (target file, stub at line 107-113)
- `backend/app/models/schemas.py` (DrugInfo model)
