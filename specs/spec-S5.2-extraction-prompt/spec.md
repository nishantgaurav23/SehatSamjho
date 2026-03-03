# Spec S5.2 — Extraction Prompt

## Overview
Builds the system prompt used to instruct GPT-4O Vision when extracting structured medical data from prescription images. The prompt defines a medical document reader persona, requires structured JSON output with per-field confidence scores, and explicitly instructs the model to never guess low-confidence dosages as definitive. The output schema matches `PrescriptionData` from S2.4.

## Dependencies
- **S5.1** — OpenAI async client init (`_get_client()`, `_reset_client()`)

## Target Location
- `backend/app/services/extraction.py`

---

## Functional Requirements

### FR-1: `EXTRACTION_SYSTEM_PROMPT` constant
- **What**: Module-level string constant containing the system prompt for GPT-4O Vision extraction
- **Content requirements**:
  - Persona: "You are a medical document reader specializing in Indian prescriptions"
  - Instruction: extract structured data from the image as JSON
  - Output must follow the `PrescriptionData` JSON schema exactly
  - Confidence scores: assign a `confidence` score (0.0–1.0) per `MedicineEntry` field group and an `overall_confidence` for the full document
  - Low-confidence rule: if a dosage, frequency, or duration is unclear, set `confidence` below 0.5 and leave the field as `null` rather than guessing
  - `doc_type` detection: set to `"prescription"`, `"lab_report"`, or `"other"` based on document content
  - Instruct the model to return ONLY valid JSON — no markdown fences, no commentary
- **Type**: `str`

### FR-2: `EXTRACTION_OUTPUT_SCHEMA` constant
- **What**: Module-level string constant containing the expected JSON schema description for the output, matching `PrescriptionData`
- **Content requirements**:
  - Top-level fields: `doctor_name` (str|null), `patient_name` (str|null), `date` (str|null), `diagnosis` (str|null), `medicines` (list), `overall_confidence` (float 0.0–1.0), `doc_type` (str)
  - Each `medicines` entry: `medicine_name` (str, required), `dosage` (str|null), `frequency` (str|null), `duration` (str|null), `instructions` (str|null), `confidence` (float 0.0–1.0)
- **Type**: `str`

### FR-3: `_build_extraction_prompt()` function
- **What**: Builds the complete prompt messages list for the GPT-4O Vision API call
- **Signature**: `_build_extraction_prompt() -> list[dict[str, str]]`
- **Returns**: A list containing a single system message dict: `[{"role": "system", "content": <combined prompt>}]`
- **Content**: Combines `EXTRACTION_SYSTEM_PROMPT` and `EXTRACTION_OUTPUT_SCHEMA` into the system message content
- **Edge cases**: Function is pure (no I/O, no settings access) — fully deterministic

---

## Tangible Outcomes

- [ ] **Outcome 1**: `EXTRACTION_SYSTEM_PROMPT` is a non-empty module-level string constant in `extraction.py`
- [ ] **Outcome 2**: `EXTRACTION_OUTPUT_SCHEMA` is a non-empty module-level string constant describing the JSON schema
- [ ] **Outcome 3**: `_build_extraction_prompt()` returns a list with exactly one system message dict
- [ ] **Outcome 4**: The system message content includes the persona instruction ("medical document reader")
- [ ] **Outcome 5**: The system message content includes the low-confidence rule (don't guess dosages)
- [ ] **Outcome 6**: The system message content includes all `PrescriptionData` field names
- [ ] **Outcome 7**: The system message content includes all `MedicineEntry` field names
- [ ] **Outcome 8**: The system message content instructs JSON-only output (no markdown fences)
- [ ] **Outcome 9**: The system message content includes `doc_type` detection instruction
- [ ] **Outcome 10**: The function is pure — no external calls, no side effects

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_extraction_system_prompt_exists**: `EXTRACTION_SYSTEM_PROMPT` is a non-empty string
2. **test_extraction_system_prompt_has_persona**: contains "medical document reader" (case-insensitive)
3. **test_extraction_system_prompt_has_confidence_rule**: mentions confidence scoring
4. **test_extraction_system_prompt_low_confidence_dosage_rule**: instructs not to guess low-confidence dosages
5. **test_extraction_system_prompt_json_only**: instructs JSON-only output, no markdown
6. **test_extraction_system_prompt_doc_type**: mentions doc_type detection (prescription, lab_report, other)
7. **test_extraction_output_schema_exists**: `EXTRACTION_OUTPUT_SCHEMA` is a non-empty string
8. **test_extraction_output_schema_has_prescription_fields**: contains all PrescriptionData top-level field names
9. **test_extraction_output_schema_has_medicine_fields**: contains all MedicineEntry field names
10. **test_build_extraction_prompt_returns_list**: returns a list
11. **test_build_extraction_prompt_single_system_message**: list has exactly one element with `role=system`
12. **test_build_extraction_prompt_content_not_empty**: system message `content` is a non-empty string
13. **test_build_extraction_prompt_contains_persona**: content includes the persona instruction
14. **test_build_extraction_prompt_contains_schema**: content includes all PrescriptionData field names
15. **test_build_extraction_prompt_contains_low_confidence_rule**: content includes the low-confidence instruction
16. **test_build_extraction_prompt_is_pure**: calling twice returns equal results (deterministic)
17. **test_build_extraction_prompt_no_side_effects**: calling does not modify module state (`_client` stays unchanged)
18. **test_extraction_system_prompt_no_phi_instruction**: prompt instructs model not to invent patient details
19. **test_extraction_output_schema_confidence_range**: schema mentions 0.0–1.0 range for confidence
20. **test_build_extraction_prompt_message_structure**: each message has exactly `role` and `content` keys

### Mocking Strategy
- No mocking needed — all functions and constants are pure (no I/O, no external services)

### Coverage Expectation
- 100% — pure functions and constants, fully testable without mocks

---

## References
- `roadmap.md` — S5.2 row (Phase 5, GPT-4O Vision Extraction)
- `backend/app/models/schemas.py` — `PrescriptionData`, `MedicineEntry` definitions
- `backend/app/services/extraction.py` — existing S5.1 client code
