# Spec S8.4 — enrich prescription

## Overview
For each `MedicineEntry` in a `PrescriptionData` object, call `lookup_drug()` to retrieve enrichment data. Run all lookups concurrently with `asyncio.gather`. Return a `List[DrugInfo | None]` aligned positionally with the input medicines list (index 0 of medicines maps to index 0 of results). This is the public orchestration API that Phase 10 uses to enrich extracted prescriptions before translation.

## Dependencies
- S8.3 (`lookup_drug()` — single-drug Redis + API lookup)
- S2.4 (Pydantic models: `PrescriptionData`, `MedicineEntry`, `DrugInfo`)

## Target Location
`backend/app/services/drug_lookup.py`

---

## Functional Requirements

### FR-1: `enrich_prescription()` function signature
- **What**: Async function `enrich_prescription(redis_client, prescription: PrescriptionData, request_id: str | None = None) -> list[DrugInfo | None]`
- **Inputs**: Redis client, `PrescriptionData` object, optional `request_id` for log correlation
- **Outputs**: List of `DrugInfo | None` — same length as `prescription.medicines`, positionally aligned
- **Edge cases**: Empty medicines list returns empty list

### FR-2: Concurrent lookups via `asyncio.gather`
- **What**: All `lookup_drug()` calls run concurrently using `asyncio.gather(*tasks)`, not sequentially
- **Inputs**: Each `MedicineEntry.medicine_name` passed to `lookup_drug()`
- **Outputs**: Gathered results in original order
- **Edge cases**: If one lookup fails/returns None, others still succeed (independent)

### FR-3: Positional alignment
- **What**: Result list index matches input medicines list index. If medicines[2] has no drug data, results[2] is `None`
- **Inputs**: N medicines
- **Outputs**: Exactly N results
- **Edge cases**: Duplicate medicine names still produce separate lookups and separate results

### FR-4: Error resilience
- **What**: Individual lookup failures must not crash the entire enrichment. `lookup_drug()` already returns `None` on failure, but `enrich_prescription()` should also catch any unexpected exception from gather
- **Inputs**: Corrupted Redis, network errors
- **Outputs**: Returns partial results or list of Nones rather than raising
- **Edge cases**: If `asyncio.gather` itself fails, return list of Nones for all medicines

### FR-5: Logging
- **What**: Log start (count of medicines), completion (count of hits vs misses), and request_id
- **Inputs**: request_id passed through
- **Outputs**: Loguru info/debug messages with request_id context
- **Edge cases**: Zero medicines logged at debug level (no-op)

---

## Tangible Outcomes

- [ ] **Outcome 1**: `enrich_prescription` is importable from `backend.app.services.drug_lookup`
- [ ] **Outcome 2**: Returns `list[DrugInfo | None]` with length == `len(prescription.medicines)`
- [ ] **Outcome 3**: Lookups run concurrently (verified by checking `asyncio.gather` is called)
- [ ] **Outcome 4**: Empty prescription.medicines returns `[]` immediately
- [ ] **Outcome 5**: Partial failures produce `None` entries without crashing
- [ ] **Outcome 6**: Logs include request_id and hit/miss counts

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_enrich_prescription_importable**: Function importable from module
2. **test_enrich_prescription_is_async**: Verify it's a coroutine function
3. **test_enrich_prescription_signature**: Accepts redis_client, prescription, request_id params
4. **test_enrich_prescription_empty_medicines**: Empty medicines list returns `[]`
5. **test_enrich_prescription_single_medicine_found**: One medicine, Redis has data -> `[DrugInfo]`
6. **test_enrich_prescription_single_medicine_not_found**: One medicine, not in Redis -> `[None]`
7. **test_enrich_prescription_multiple_medicines_all_found**: 3 medicines, all found -> 3 DrugInfos
8. **test_enrich_prescription_multiple_medicines_mixed**: 3 medicines, 2 found + 1 not -> [DrugInfo, None, DrugInfo]
9. **test_enrich_prescription_multiple_medicines_none_found**: 3 medicines, none found -> [None, None, None]
10. **test_enrich_prescription_positional_alignment**: Result indices match input indices exactly
11. **test_enrich_prescription_concurrent_gather**: Verify `asyncio.gather` is used (mock + assert)
12. **test_enrich_prescription_passes_request_id**: request_id forwarded to each `lookup_drug()` call
13. **test_enrich_prescription_passes_redis_client**: Redis client forwarded to each `lookup_drug()` call
14. **test_enrich_prescription_result_length_matches_input**: Output list length always equals medicines count
15. **test_enrich_prescription_duplicate_names**: Duplicate medicine names produce separate lookups
16. **test_enrich_prescription_gather_exception_resilience**: If gather raises, returns list of Nones
17. **test_enrich_prescription_logs_start**: Logs medicine count at start
18. **test_enrich_prescription_logs_completion**: Logs hit/miss counts on completion
19. **test_enrich_prescription_logs_request_id**: request_id appears in log messages
20. **test_enrich_prescription_returns_list_type**: Return type is always a list (never None)

### Mocking Strategy
- Mock `lookup_drug()` at `backend.app.services.drug_lookup.lookup_drug` to control per-medicine results
- Mock `asyncio.gather` only for the concurrency verification test
- No real Redis needed — `lookup_drug` is fully mocked

### Coverage Expectation
- All public functions have at least one test; edge cases covered
- 20 tests total

---

## References
- roadmap.md (S8.4 row)
- `backend/app/services/drug_lookup.py` (target file, S8.2 + S8.3 already implemented)
- `backend/app/models/schemas.py` (PrescriptionData, MedicineEntry, DrugInfo)
