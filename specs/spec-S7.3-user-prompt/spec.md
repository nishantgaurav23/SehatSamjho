# Spec S7.3 — User Prompt Builder

## Overview
Builds the user-turn prompt for the Claude Sonnet 4.6 translation call. Serializes `PrescriptionData` (from GPT-4O extraction), an optional list of `DrugInfo` (from drug lookup), and a `glossary_context` string (from Phase 6) into a structured text block. The language target is placed in the prompt header so Claude knows which language to output. Low-confidence fields (confidence < 0.7) are explicitly labelled with a warning marker so Claude flags them in the response.

## Dependencies
- **S7.1** — Anthropic client + constants (done)
- **S2.4** — Pydantic models: `PrescriptionData`, `DrugInfo`, `MedicineEntry` (done)

## Target Location
`backend/app/services/translation.py`

---

## Functional Requirements

### FR-1: `_build_user_prompt()` function signature
- **What**: A module-level function `_build_user_prompt()` that builds the user-turn string for the Claude API call.
- **Inputs**:
  - `prescription: PrescriptionData` — extracted prescription data
  - `language_name: str` — target language display name (e.g., "Hindi", "Tamil")
  - `language_code: str` — target language code (e.g., "hi", "ta")
  - `drug_info_list: list[DrugInfo] | None = None` — optional enrichment data per medicine
  - `glossary_context: str = ""` — optional pre-formatted glossary block
- **Outputs**: `str` — fully rendered user prompt
- **Edge cases**: Empty medicines list, None drug_info_list, empty glossary_context

### FR-2: Language target header
- **What**: The prompt must begin with a clear language target directive so Claude knows which language to translate into.
- **Format**: `"Translate the following prescription into {language_name} ({language_code})."`
- **Edge cases**: Language name/code always present (validated upstream)

### FR-3: Prescription data section
- **What**: Serialize the prescription metadata and medicines list into a structured text block.
- **Format**:
  ```
  ## Prescription Details
  Doctor: {doctor_name or "Not specified"}
  Date: {date or "Not specified"}
  Diagnosis: {diagnosis or "Not specified"}
  Overall Confidence: {overall_confidence}
  ```
- **Edge cases**: All optional fields may be None — use "Not specified" placeholder
- **Note**: `patient_name` is NEVER included (PHI protection)

### FR-4: Medicine entries serialization
- **What**: Each `MedicineEntry` is serialized as a numbered item with all available fields.
- **Format** (per medicine):
  ```
  ### Medicine {n}: {medicine_name}
  - Dosage: {dosage or "Not specified"}
  - Frequency: {frequency or "Not specified"}
  - Duration: {duration or "Not specified"}
  - Instructions: {instructions or "Not specified"}
  - Confidence: {confidence}
  ```
- **Low-confidence marking**: If `confidence < 0.7`, prepend the medicine header with `[LOW CONFIDENCE]` so Claude knows to flag it with a warning in the output.

### FR-5: Drug enrichment section
- **What**: When `drug_info_list` is provided and non-empty, append a drug enrichment section with matched drug information for each medicine.
- **Format**:
  ```
  ## Drug Information
  ### {brand_name}
  - Generic Name: {generic_name or "Unknown"}
  - Therapeutic Class: {therapeutic_class or "Unknown"}
  - Purpose: {purpose_en or "Unknown"}
  - Side Effects: {side_effects_en or "Unknown"}
  - Timing: {timing_instructions or "Unknown"}
  - Known Interactions: {known_interactions or "None known"}
  ```
- **Edge cases**: `drug_info_list` is None or empty — omit entire section. List may be shorter than medicines list (some drugs not found) — only include entries that are not None.

### FR-6: Glossary context section
- **What**: When `glossary_context` is non-empty, append it as a reference section.
- **Format**:
  ```
  ## Glossary Reference
  {glossary_context}
  ```
- **Edge cases**: Empty or whitespace-only glossary_context — omit entire section.

### FR-7: No PHI in prompt
- **What**: The function must never include `patient_name` or any raw phone number in the output prompt. Only medical data and metadata.

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_build_user_prompt` is importable from `backend.app.services.translation`
- [ ] **Outcome 2**: Output starts with language target directive containing language_name and language_code
- [ ] **Outcome 3**: Prescription metadata (doctor, date, diagnosis, confidence) is present; patient_name is never included
- [ ] **Outcome 4**: Each medicine is serialized with all fields; low-confidence items marked with `[LOW CONFIDENCE]`
- [ ] **Outcome 5**: Drug enrichment section appears only when drug_info_list has entries
- [ ] **Outcome 6**: Glossary section appears only when glossary_context is non-empty
- [ ] **Outcome 7**: Empty medicines list produces a valid prompt with no medicine entries
- [ ] **Outcome 8**: Function is pure (no side effects, no I/O, no logging)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_import_and_callable**: `_build_user_prompt` is importable and callable
2. **test_signature_params**: Accepts prescription, language_name, language_code, optional drug_info_list, optional glossary_context
3. **test_returns_string**: Returns a non-empty string
4. **test_language_header_present**: Output starts with language target directive
5. **test_language_header_contains_name_and_code**: Language name and code both present in header
6. **test_prescription_metadata_present**: Doctor, date, diagnosis, overall_confidence in output
7. **test_patient_name_excluded**: patient_name never appears in output (PHI safety)
8. **test_none_metadata_shows_not_specified**: None fields render as "Not specified"
9. **test_medicine_entry_serialized**: Medicine name, dosage, frequency, duration, instructions, confidence all present
10. **test_multiple_medicines_numbered**: Multiple medicines are numbered sequentially
11. **test_low_confidence_medicine_marked**: Confidence < 0.7 triggers `[LOW CONFIDENCE]` marker
12. **test_high_confidence_medicine_not_marked**: Confidence >= 0.7 does not have marker
13. **test_drug_info_section_present**: Drug info section appears when drug_info_list provided
14. **test_drug_info_fields_present**: All DrugInfo fields rendered
15. **test_drug_info_none_omitted**: Section omitted when drug_info_list is None
16. **test_drug_info_empty_list_omitted**: Section omitted when drug_info_list is empty []
17. **test_glossary_section_present**: Glossary section appears when glossary_context non-empty
18. **test_glossary_section_omitted_empty**: Section omitted when glossary_context is ""
19. **test_empty_medicines_list**: Works with prescription that has empty medicines list
20. **test_pure_function_no_side_effects**: Calling twice with same input produces identical output

### Mocking Strategy
- **No mocking needed** — `_build_user_prompt()` is a pure function operating on Pydantic models only.

### Coverage Expectation
- All public function branches covered; all edge cases for None/empty fields tested.

---

## References
- roadmap.md Phase 7 — Translation
- S7.1 spec (Anthropic client + constants)
- S7.2 spec (system prompt builder)
- S2.4 spec (Pydantic models: PrescriptionData, DrugInfo, MedicineEntry)
