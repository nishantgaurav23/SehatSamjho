# Spec S5.1 — OpenAI Async Client Init

## Overview

Initialises the OpenAI async client used for GPT-4O Vision prescription extraction. Provides a module-level lazy singleton via `_get_client()` so the client is created on first use, uses the API key from pydantic-settings config, and is easily replaceable in tests via mock patching.

## Dependencies

- **S1.3** — pydantic-settings config (`settings.OPENAI_API_KEY`)
- **S2.4** — Pydantic models (`PrescriptionData`, `MedicineEntry` used by downstream specs)

## Target Location

`backend/app/services/extraction.py`

---

## Functional Requirements

### FR-1: Module-level lazy singleton client

- **What**: A private function `_get_client()` returns an `openai.AsyncOpenAI` instance. On first call it creates the client with `api_key=settings.OPENAI_API_KEY` and caches it in a module-level variable `_client`. Subsequent calls return the cached instance.
- **Inputs**: None (reads `settings.OPENAI_API_KEY` internally via lazy import)
- **Outputs**: `openai.AsyncOpenAI` instance
- **Edge cases**:
  - If `OPENAI_API_KEY` is empty/missing, the `Settings` class already raises a validation error at import time (covered by S1.3).
  - Thread safety is not required (single async event loop).

### FR-2: Lazy config import

- **What**: The `settings` object must be imported lazily inside `_get_client()` (not at module level) to avoid import-time side effects in tests that don't set env vars. This follows the same pattern used in `whatsapp.py`.
- **Inputs**: N/A
- **Outputs**: N/A
- **Edge cases**: Tests that import `extraction` module should not trigger `Settings()` construction.

### FR-3: Client reset for testing

- **What**: A private function `_reset_client()` sets the module-level `_client` back to `None`, allowing tests to force re-creation with different mocked settings.
- **Inputs**: None
- **Outputs**: None (side effect: `_client = None`)

### FR-4: Module docstring and structure

- **What**: The module `extraction.py` must have a docstring identifying it as the GPT-4O Vision extraction service. It should import `openai` and `loguru.logger`. The file acts as the foundation for S5.2–S5.5 which add the extraction prompt, vision call, orchestrator, and error handling.
- **Inputs**: N/A
- **Outputs**: N/A

---

## Tangible Outcomes

- [ ] **Outcome 1**: `backend/app/services/extraction.py` exists and is importable
- [ ] **Outcome 2**: `_get_client()` returns an `openai.AsyncOpenAI` instance
- [ ] **Outcome 3**: Calling `_get_client()` twice returns the same object (singleton)
- [ ] **Outcome 4**: `_reset_client()` clears the cached client so the next `_get_client()` creates a new one
- [ ] **Outcome 5**: `settings` is NOT imported at module level (lazy import inside `_get_client()`)
- [ ] **Outcome 6**: The client is created with `api_key` matching `settings.OPENAI_API_KEY`
- [ ] **Outcome 7**: Importing the module does not trigger `Settings()` construction

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

1. **test_extraction_module_importable**: `import backend.app.services.extraction` succeeds
2. **test_get_client_returns_async_openai**: `_get_client()` returns an `openai.AsyncOpenAI` instance
3. **test_get_client_singleton**: Two calls to `_get_client()` return the same object (`is` identity)
4. **test_get_client_uses_api_key**: The returned client has `api_key` set to the mocked `OPENAI_API_KEY` value
5. **test_reset_client_clears_cache**: After `_reset_client()`, `_get_client()` creates a new instance (different `id`)
6. **test_get_client_lazy_settings_import**: Importing `extraction` does not call `Settings()` — mock `Settings` and verify it's not called at import time
7. **test_get_client_creates_client_with_correct_args**: Verify `openai.AsyncOpenAI` is called with `api_key=<mocked_key>`
8. **test_module_has_docstring**: `extraction.__doc__` is non-empty
9. **test_module_exposes_expected_names**: Module has `_get_client` and `_reset_client` in its namespace
10. **test_get_client_after_reset_uses_fresh_settings**: After reset, a new call reads settings again (verifiable by changing mocked key)

### Mocking Strategy

- **Settings**: Mock `backend.app.core.config.Settings` or patch `settings.OPENAI_API_KEY` to avoid needing real env vars
- **openai.AsyncOpenAI**: For tests that check constructor args, mock the `AsyncOpenAI` class and inspect call args
- **No real API calls**: The client is only instantiated, never used to make calls in this spec

### Coverage Expectation

- All public and private functions (`_get_client`, `_reset_client`) tested
- Singleton behavior, lazy import, and reset functionality fully covered
- 10 tests minimum

---

## References

- roadmap.md — Phase 5: GPT-4O Vision Extraction
- `backend/app/core/config.py` — `Settings.OPENAI_API_KEY`
- `backend/app/models/schemas.py` — `PrescriptionData`, `MedicineEntry`
- `backend/app/services/whatsapp.py` — lazy settings import pattern (precedent)
