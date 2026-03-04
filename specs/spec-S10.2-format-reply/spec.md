# Spec S10.2 — Format Reply

## Overview
Builds the patient-facing WhatsApp text message from pipeline results. Constructs a structured body with a greeting, per-medicine cards (name in English + purpose in patient's language + dosage), low-confidence warnings flagged with a warning symbol, and a disclaimer. The formatted message must respect the WhatsApp message limit of 1600 characters, truncating gracefully if needed.

## Dependencies
- S10.1 (Pipeline wiring) — provides `PrescriptionData`, `DrugInfo` list, and `TranslationResult` to format
- S2.4 (Pydantic models) — `PrescriptionData`, `MedicineEntry`, `DrugInfo`, `TranslationResult`

## Target Location
`backend/app/api/webhooks.py` — new function `_format_reply()`, wired into `_run_pipeline()`

---

## Functional Requirements

### FR-1: Function signature
- **What**: `_format_reply(prescription: PrescriptionData, drug_info_list: list[DrugInfo | None], translation: TranslationResult, language_name: str) -> str`
- **Inputs**: Prescription data, aligned drug info list (may contain `None` for unmatched drugs), translation result, and the patient's chosen language name
- **Outputs**: A formatted string ready to send as a WhatsApp text message
- **Edge cases**: Empty medicines list, all None drug info, very long medicine names

### FR-2: Greeting section
- **What**: Open with a brief greeting line referencing the patient's language
- **Inputs**: `language_name` (e.g. "Hindi", "Tamil")
- **Outputs**: A line like "Here is your prescription summary:" (language-neutral, since the translated_text is already in the patient's language)
- **Edge cases**: None — always present

### FR-3: Per-medicine cards
- **What**: For each medicine in `prescription.medicines`, build a compact card showing:
  - Medicine name (English, from `MedicineEntry.medicine_name`)
  - Purpose in patient's language (from corresponding `TranslationResult.per_medicine_summaries[i]` if available)
  - Dosage (from `MedicineEntry.dosage` if present)
  - Frequency (from `MedicineEntry.frequency` if present)
  - Duration (from `MedicineEntry.duration` if present)
- **Inputs**: `prescription.medicines` (list of MedicineEntry), `translation.per_medicine_summaries` (list of str, aligned by index), `drug_info_list` (aligned by index)
- **Outputs**: Multi-line card per medicine, separated by blank lines
- **Edge cases**: Missing dosage/frequency/duration fields (omit line), per_medicine_summaries shorter than medicines list (skip summary for those), drug_info is None (skip purpose fallback from DrugInfo)

### FR-4: Low-confidence warnings
- **What**: If a medicine's `confidence < 0.7`, prepend its card with a warning indicator and append a note: "This item could not be read clearly — please verify with your doctor/pharmacist"
- **Inputs**: `MedicineEntry.confidence` per medicine
- **Outputs**: Warning text on affected medicine cards
- **Edge cases**: All medicines high-confidence (no warnings), all low-confidence (all flagged), confidence exactly 0.7 (not flagged — strictly less than)

### FR-5: Disclaimer section
- **What**: Append the disclaimer from `TranslationResult.disclaimer` at the end, separated by a blank line
- **Inputs**: `translation.disclaimer`
- **Outputs**: Disclaimer text as the final section of the message
- **Edge cases**: None — disclaimer is always present (required field)

### FR-6: WhatsApp message limit (1600 chars)
- **What**: If the fully assembled message exceeds 1600 characters, truncate gracefully:
  1. First try: omit duration/frequency details from cards (keep name + dosage only)
  2. If still over: truncate per-medicine summaries
  3. Always preserve: greeting, disclaimer, and low-confidence warnings
  4. Add a trailing note: "(Message truncated — ask for the full version)"
- **Inputs**: Assembled message string
- **Outputs**: String guaranteed to be <= 1600 characters
- **Edge cases**: Single long medicine name, many medicines (10+), extremely long disclaimer

### FR-7: Wire into pipeline
- **What**: Replace the direct `translation_result.translated_text` send in `_run_pipeline()` with a call to `_format_reply()` for the text message body
- **Inputs**: Pipeline results (prescription_data, drug_info_list, translation_result, session.language_name)
- **Outputs**: Formatted reply sent via `send_text_message()`
- **Edge cases**: None — straightforward wiring

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_format_reply()` is importable and callable with the correct signature
- [ ] **Outcome 2**: Output contains a greeting section as the first line
- [ ] **Outcome 3**: Each medicine gets a distinct card block with name and available details
- [ ] **Outcome 4**: Medicines with confidence < 0.7 have a warning indicator in their card
- [ ] **Outcome 5**: Disclaimer appears at the end of the message
- [ ] **Outcome 6**: Output never exceeds 1600 characters, even with many medicines
- [ ] **Outcome 7**: `_run_pipeline()` uses `_format_reply()` instead of raw `translated_text`
- [ ] **Outcome 8**: Empty medicines list produces a valid message (greeting + translated_text + disclaimer)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_format_reply_importable**: `_format_reply` exists and is callable
2. **test_format_reply_signature**: Accepts (PrescriptionData, list, TranslationResult, str) and returns str
3. **test_format_reply_async_or_sync**: Verify it's a regular (sync) function (pure formatting, no I/O)
4. **test_greeting_present**: Output starts with a greeting line
5. **test_medicine_card_name**: Each medicine name appears in the output
6. **test_medicine_card_dosage**: Dosage appears in the card when present
7. **test_medicine_card_frequency**: Frequency appears in the card when present
8. **test_medicine_card_duration**: Duration appears in the card when present
9. **test_medicine_card_missing_fields**: Missing optional fields are gracefully omitted (no "None" text)
10. **test_per_medicine_summary**: Per-medicine summaries from translation appear in cards
11. **test_per_medicine_summary_shorter**: Handles per_medicine_summaries shorter than medicines list
12. **test_low_confidence_warning**: Confidence < 0.7 triggers warning text in card
13. **test_high_confidence_no_warning**: Confidence >= 0.7 has no warning
14. **test_confidence_boundary_0_7**: Confidence exactly 0.7 does NOT trigger warning
15. **test_disclaimer_present**: Disclaimer appears at end of output
16. **test_max_length_1600**: Output with many medicines is <= 1600 chars
17. **test_truncation_note**: When truncated, includes truncation note
18. **test_empty_medicines**: Empty medicines list produces valid output
19. **test_no_phi_in_output**: Patient name and doctor name do NOT appear in formatted reply
20. **test_pipeline_uses_format_reply**: `_run_pipeline` calls `_format_reply` (mock-based verification)

### Mocking Strategy
- No external services needed for FR-1 through FR-6 (pure function)
- FR-7 (pipeline wiring test): mock `_format_reply`, `send_text_message`, and all pipeline services
- Build test fixtures with `PrescriptionData`, `DrugInfo`, and `TranslationResult` instances

### Coverage Expectation
- All public and private formatting logic covered
- Edge cases: empty lists, missing fields, truncation boundary, confidence boundary

---

## References
- roadmap.md (S10.2 row)
- S10.1 spec (pipeline wiring — upstream)
- S2.4 spec (Pydantic models — MedicineEntry, DrugInfo, TranslationResult)
- WhatsApp Business API message size limit: 1600 characters
