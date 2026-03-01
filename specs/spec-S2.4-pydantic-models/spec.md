# Spec S2.4 — Pydantic Models

## Overview
Defines all Pydantic request/response models used across the SehatSamjho backend. These schemas form the shared data contract between extraction, translation, drug lookup, TTS, and webhook services. Includes: `MedicineEntry`, `PrescriptionData`, `DrugInfo`, `TranslationResult`, `WebhookPayload`, `SessionState` (with `SessionStatus` enum), and `GlossaryEntry`. All models use strict Pydantic v2 conventions with type annotations and validation.

## Dependencies
- **S1.1** (Dependency declaration) — pydantic is declared in pyproject.toml

## Target Location
- `backend/app/models/schemas.py`

---

## Functional Requirements

### FR-1: SessionStatus Enum
- **What**: String enum defining WhatsApp conversation session states
- **Values**: `WAITING_FOR_LANGUAGE`, `WAITING_FOR_IMAGE`, `PROCESSING`
- **Usage**: Stored in `SessionState`, drives webhook state machine dispatch (Phase 4)

### FR-2: MedicineEntry Model
- **What**: A single medicine extracted from a prescription image
- **Fields**:
  - `medicine_name: str` — brand or generic name as printed
  - `dosage: str | None` — e.g. "500mg", "10ml" (None if unreadable)
  - `frequency: str | None` — e.g. "twice daily", "1-0-1" (None if unreadable)
  - `duration: str | None` — e.g. "5 days", "1 month" (None if unreadable)
  - `instructions: str | None` — e.g. "after food", "at bedtime"
  - `confidence: float` — GPT-4O extraction confidence (0.0–1.0)
- **Validation**: `confidence` must be between 0.0 and 1.0 (inclusive)
- **Edge cases**: `medicine_name` must be non-empty string

### FR-3: PrescriptionData Model
- **What**: Full structured output from GPT-4O Vision extraction
- **Fields**:
  - `doctor_name: str | None` — extracted doctor name
  - `patient_name: str | None` — extracted patient name (not stored in DB — ephemeral only)
  - `date: str | None` — prescription date as string
  - `diagnosis: str | None` — stated diagnosis or condition
  - `medicines: list[MedicineEntry]` — list of extracted medicines
  - `overall_confidence: float` — average confidence across all fields (0.0–1.0)
  - `doc_type: str` — detected document type, default "prescription"
- **Validation**: `overall_confidence` between 0.0 and 1.0; `medicines` list can be empty (e.g. lab report)

### FR-4: DrugInfo Model
- **What**: Enrichment data for a medicine from drug lookup service
- **Fields**:
  - `brand_name: str` — commercial brand name
  - `generic_name: str | None` — generic/chemical name
  - `therapeutic_class: str | None` — drug category (e.g. "Analgesic")
  - `purpose_en: str | None` — English purpose description
  - `side_effects_en: str | None` — common side effects in English
  - `timing_instructions: str | None` — when to take (e.g. "before meals")
  - `known_interactions: str | None` — drug interactions warning
- **Edge cases**: `brand_name` must be non-empty; all other fields optional

### FR-5: GlossaryEntry Model
- **What**: A single medical term with plain-language explanation and vernacular translation
- **Fields**:
  - `term: str` — medical term in English (e.g. "hypertension")
  - `explanation: str` — plain-language English explanation
  - `vernacular: str` — translation/explanation in the target language
- **Validation**: All three fields required, non-empty

### FR-6: TranslationResult Model
- **What**: Output from Claude Sonnet 4.6 translation service
- **Fields**:
  - `translated_text: str` — full plain-language translation in target language
  - `per_medicine_summaries: list[str]` — one summary string per medicine
  - `disclaimer: str` — mandatory medical disclaimer text
  - `language_code: str` — target language code (e.g. "hi", "ta")
- **Validation**: `translated_text` and `disclaimer` must be non-empty

### FR-7: WebhookPayload Model
- **What**: Parsed incoming Twilio WhatsApp webhook form data
- **Fields**:
  - `from_number: str` — sender's WhatsApp number (e.g. "whatsapp:+919876543210")
  - `body: str` — message text (empty string if image-only)
  - `num_media: int` — number of media attachments (default 0)
  - `media_url: str | None` — URL of first media attachment (if any)
  - `media_content_type: str | None` — MIME type of first media (e.g. "image/jpeg")
- **Validation**: `from_number` must be non-empty; `num_media` >= 0; `body` defaults to ""

### FR-8: SessionState Model
- **What**: WhatsApp conversation session stored in Redis
- **Fields**:
  - `status: SessionStatus` — current state in the conversation flow
  - `language_code: str | None` — selected language code (None until chosen)
  - `language_name: str | None` — selected language display name
  - `request_id: str | None` — UUID for log correlation during pipeline processing
  - `created_at: str` — ISO 8601 timestamp of session creation
- **Serialization**: Must support `model_dump_json()` for Redis storage and `model_validate_json()` for Redis retrieval
- **Edge cases**: New sessions start with `status=WAITING_FOR_LANGUAGE`, `language_code=None`

---

## Tangible Outcomes

- [ ] **Outcome 1**: `from backend.app.models.schemas import SessionStatus, MedicineEntry, PrescriptionData, DrugInfo, GlossaryEntry, TranslationResult, WebhookPayload, SessionState` imports successfully
- [ ] **Outcome 2**: All models can be instantiated with valid data and round-trip through `model_dump()` / `model_validate()`
- [ ] **Outcome 3**: All models can round-trip through `model_dump_json()` / `model_validate_json()` (JSON serialization)
- [ ] **Outcome 4**: Validation rejects invalid data (e.g. confidence out of range, empty required strings, negative num_media)
- [ ] **Outcome 5**: `SessionState` can serialize to JSON string for Redis and deserialize back with all fields intact
- [ ] **Outcome 6**: `PrescriptionData` with zero medicines is valid (lab report edge case)
- [ ] **Outcome 7**: `WebhookPayload` handles image-only messages (empty body, num_media=1)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

#### SessionStatus Enum
1. **test_session_status_values**: Verify all three enum values exist: WAITING_FOR_LANGUAGE, WAITING_FOR_IMAGE, PROCESSING
2. **test_session_status_is_string_enum**: Verify enum values are strings (for JSON serialization)

#### MedicineEntry
3. **test_medicine_entry_valid**: Create with all fields, verify round-trip
4. **test_medicine_entry_minimal**: Create with only required fields (medicine_name, confidence), optional fields are None
5. **test_medicine_entry_confidence_range**: Reject confidence < 0.0 and > 1.0
6. **test_medicine_entry_empty_name_rejected**: Reject empty string for medicine_name

#### PrescriptionData
7. **test_prescription_data_full**: Create with all fields including medicines list
8. **test_prescription_data_empty_medicines**: Valid with empty medicines list (lab report)
9. **test_prescription_data_confidence_range**: Reject overall_confidence out of [0.0, 1.0]
10. **test_prescription_data_default_doc_type**: Default doc_type is "prescription"

#### DrugInfo
11. **test_drug_info_valid**: Create with all fields
12. **test_drug_info_minimal**: Only brand_name required, rest optional
13. **test_drug_info_empty_brand_rejected**: Reject empty brand_name

#### GlossaryEntry
14. **test_glossary_entry_valid**: Create with all three fields
15. **test_glossary_entry_empty_fields_rejected**: Reject empty term, explanation, or vernacular

#### TranslationResult
16. **test_translation_result_valid**: Create with all fields
17. **test_translation_result_empty_text_rejected**: Reject empty translated_text
18. **test_translation_result_empty_disclaimer_rejected**: Reject empty disclaimer

#### WebhookPayload
19. **test_webhook_payload_full**: Create with all fields including media
20. **test_webhook_payload_text_only**: No media (num_media=0, media_url=None)
21. **test_webhook_payload_image_only**: Empty body, num_media=1, media_url set
22. **test_webhook_payload_negative_num_media_rejected**: Reject num_media < 0
23. **test_webhook_payload_empty_from_rejected**: Reject empty from_number

#### SessionState
24. **test_session_state_valid**: Create with all fields
25. **test_session_state_new_session_defaults**: New session: WAITING_FOR_LANGUAGE, language_code=None
26. **test_session_state_json_round_trip**: model_dump_json() → model_validate_json() preserves all fields
27. **test_session_state_status_enum_serialized**: JSON output includes string enum value

### Mocking Strategy
- No external services needed — pure Pydantic model tests
- No mocking required

### Coverage Expectation
- All 8 models/enums have at least 2 tests each
- Validation edge cases (boundary values, empty strings, type errors) covered
- JSON serialization round-trip verified for all models

---

## References
- roadmap.md — S2.4 spec row
- `backend/app/db/models.py` — InteractionStatus enum (similar pattern for SessionStatus)
- Phase 3–10 specs consume these models as inputs/outputs
