# Spec S7.1 — Anthropic Async Client + Prompt Templates

## Overview

Initialises the Anthropic async client used for Claude Sonnet 4.6 translation and text-based AI calls. Provides a module-level lazy singleton via `_get_client()` (mirroring the S5.1 OpenAI pattern), uses the API key from pydantic-settings config, and stores system + user prompt templates as module-level constants. This module is the foundation for S7.2–S7.5 which build the full translation pipeline.

## Dependencies

- **S1.3** — pydantic-settings config (`settings.ANTHROPIC_API_KEY`)

## Target Location

`backend/app/services/translation.py`

---

## Functional Requirements

### FR-1: Module-level lazy singleton client
- **What**: A private function `_get_client()` returns an `anthropic.AsyncAnthropic` instance. On first call it creates the client with `api_key=settings.ANTHROPIC_API_KEY` and caches it in a module-level variable `_client`. Subsequent calls return the cached instance.
- **Inputs**: None (reads `settings.ANTHROPIC_API_KEY` internally via lazy import)
- **Outputs**: `anthropic.AsyncAnthropic` instance
- **Edge cases**:
  - If `ANTHROPIC_API_KEY` is empty/missing, the `Settings` class already raises a validation error at import time (covered by S1.3).
  - Thread safety is not required (single async event loop).

### FR-2: Lazy config import
- **What**: The `settings` object must be imported lazily inside `_get_client()` (not at module level) to avoid import-time side effects in tests that don't set env vars. This follows the same pattern used in `extraction.py` and `whatsapp.py`.
- **Inputs**: N/A
- **Outputs**: N/A
- **Edge cases**: Tests that import `translation` module should not trigger `Settings()` construction.

### FR-3: Client reset for testing
- **What**: A private function `_reset_client()` sets the module-level `_client` back to `None`, allowing tests to force re-creation with different mocked settings.
- **Inputs**: None
- **Outputs**: None (side effect: `_client = None`)

### FR-4: Model constant
- **What**: A module-level constant `CLAUDE_MODEL` set to `"claude-sonnet-4-6"`. Used by downstream specs (S7.4) when calling `client.messages.create()`.
- **Inputs**: N/A
- **Outputs**: N/A

### FR-5: Translation token limits
- **What**: Module-level constants for the Claude API call parameters:
  - `TRANSLATION_MAX_TOKENS: int = 1024` — maximum tokens for the translation response
  - `TRANSLATION_TEMPERATURE: float = 0.3` — low temperature for consistent medical translations
- **Inputs**: N/A
- **Outputs**: N/A

### FR-6: Module docstring and structure
- **What**: The module `translation.py` must have a docstring identifying it as the Claude Sonnet 4.6 translation service. It should import `anthropic` and `loguru.logger`. The file acts as the foundation for S7.2–S7.5 which add the system prompt, user prompt, translate orchestrator, and error handling.
- **Inputs**: N/A
- **Outputs**: N/A

---

## Tangible Outcomes

- [ ] **Outcome 1**: `backend/app/services/translation.py` exists and is importable
- [ ] **Outcome 2**: `_get_client()` returns an `anthropic.AsyncAnthropic` instance
- [ ] **Outcome 3**: Calling `_get_client()` twice returns the same object (singleton)
- [ ] **Outcome 4**: `_reset_client()` clears the cached client so the next `_get_client()` creates a new one
- [ ] **Outcome 5**: `settings` is NOT imported at module level (lazy import inside `_get_client()`)
- [ ] **Outcome 6**: The client is created with `api_key` matching `settings.ANTHROPIC_API_KEY`
- [ ] **Outcome 7**: Importing the module does not trigger `Settings()` construction
- [ ] **Outcome 8**: `CLAUDE_MODEL` equals `"claude-sonnet-4-6"`
- [ ] **Outcome 9**: `TRANSLATION_MAX_TOKENS` equals `1024`
- [ ] **Outcome 10**: `TRANSLATION_TEMPERATURE` equals `0.3`

---

## Test-Driven Requirements

### Tests to Write First (Red → Green)

1. **test_translation_module_importable**: `import backend.app.services.translation` succeeds
2. **test_get_client_returns_async_anthropic**: `_get_client()` returns an `anthropic.AsyncAnthropic` instance
3. **test_get_client_singleton**: Two calls to `_get_client()` return the same object (`is` identity)
4. **test_get_client_uses_api_key**: The returned client has `api_key` set to the mocked `ANTHROPIC_API_KEY` value
5. **test_reset_client_clears_cache**: After `_reset_client()`, `_get_client()` creates a new instance (different `id`)
6. **test_get_client_lazy_settings_import**: Importing `translation` does not call `Settings()` — mock `Settings` and verify it's not called at import time
7. **test_get_client_creates_client_with_correct_args**: Verify `anthropic.AsyncAnthropic` is called with `api_key=<mocked_key>`
8. **test_module_has_docstring**: `translation.__doc__` is non-empty
9. **test_module_exposes_expected_names**: Module has `_get_client`, `_reset_client`, `CLAUDE_MODEL`, `TRANSLATION_MAX_TOKENS`, `TRANSLATION_TEMPERATURE` in its namespace
10. **test_get_client_after_reset_uses_fresh_settings**: After reset, a new call reads settings again (verifiable by changing mocked key)
11. **test_claude_model_constant**: `CLAUDE_MODEL == "claude-sonnet-4-6"`
12. **test_translation_max_tokens_constant**: `TRANSLATION_MAX_TOKENS == 1024`
13. **test_translation_temperature_constant**: `TRANSLATION_TEMPERATURE == 0.3`

### Mocking Strategy

- **Settings**: Mock `backend.app.core.config.Settings` or patch `settings.ANTHROPIC_API_KEY` to avoid needing real env vars
- **anthropic.AsyncAnthropic**: For tests that check constructor args, mock the `AsyncAnthropic` class and inspect call args
- **No real API calls**: The client is only instantiated, never used to make calls in this spec

### Coverage Expectation

- All public and private functions (`_get_client`, `_reset_client`) tested
- All module-level constants (`CLAUDE_MODEL`, `TRANSLATION_MAX_TOKENS`, `TRANSLATION_TEMPERATURE`) tested
- Singleton behavior, lazy import, and reset functionality fully covered
- 13 tests minimum

---

## References

- roadmap.md — Phase 7: Translation
- `backend/app/core/config.py` — `Settings.ANTHROPIC_API_KEY`
- `backend/app/services/extraction.py` — `_get_client()` / `_reset_client()` pattern (precedent)
- `backend/app/services/whatsapp.py` — lazy settings import pattern (precedent)
