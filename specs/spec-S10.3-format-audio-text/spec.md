# Spec S10.3 — Format Audio Text

## Overview
Produces a clean, spoken-friendly version of the prescription summary for Bhashini TTS input. Strips emoji, markdown formatting, bullet points, and special characters. Simplifies sentence structure so the audio output sounds natural when read aloud. Currently `_run_pipeline()` passes `translation_result.translated_text` directly to TTS — this spec replaces that with a dedicated formatting step.

## Dependencies
- S7.4 (simplify_and_translate) — provides `TranslationResult` with `translated_text`, `per_medicine_summaries`, and `disclaimer`

## Target Location
`backend/app/api/webhooks.py` — new function `_format_audio_text()`, wired into `_run_pipeline()` step 5

---

## Functional Requirements

### FR-1: Function signature
- **What**: `_format_audio_text(prescription: PrescriptionData, translation: TranslationResult, language_name: str) -> str`
- **Inputs**: Prescription data (for medicine names/dosage), translation result (translated text + per-medicine summaries + disclaimer), and the patient's language name
- **Outputs**: A plain-text string suitable for TTS — no emoji, no markdown, no special Unicode characters
- **Edge cases**: Empty medicines list, empty translated_text, very long output

### FR-2: Strip emoji and special characters
- **What**: Remove all emoji (Unicode emoji ranges), markdown formatting (`*`, `**`, `_`, `#`, `` ` ``), bullet points (`-`, `*` at line start, `\u2022`), and special Unicode symbols (`\u26a0\ufe0f`, `\u2014`, etc.)
- **Inputs**: Raw text that may contain emoji and formatting
- **Outputs**: Clean text with only standard alphanumeric characters, punctuation, and the target language's script
- **Edge cases**: Text that is already clean (no-op), text that is entirely emoji (returns empty after stripping)

### FR-3: Simplify sentence structure for speech
- **What**: Convert structured card-like formatting into flowing spoken sentences:
  - Replace "Dosage: 500mg" with "dosage is 500mg"
  - Replace "Frequency: twice daily" with "to be taken twice daily"
  - Separate medicine entries with pauses (periods or "Next medicine:")
  - Add a spoken greeting prefix (e.g. "Here is your prescription summary.")
- **Inputs**: Medicine entries and translation summaries
- **Outputs**: Natural spoken text with simple sentence patterns
- **Edge cases**: Missing dosage/frequency/duration (omit gracefully), single medicine (no "Next" prefix)

### FR-4: Include spoken disclaimer
- **What**: Append a spoken-friendly version of the disclaimer at the end, prefixed with "Important note:" or similar spoken cue
- **Inputs**: `translation.disclaimer`
- **Outputs**: Disclaimer text cleaned of any formatting, appended to the audio text
- **Edge cases**: Disclaimer with emoji or markdown (strip them)

### FR-5: Length limit for TTS
- **What**: Bhashini TTS has practical limits. Cap audio text at 2000 characters. If longer, truncate at the last complete sentence before the limit and append "For full details, please read the text message."
- **Inputs**: Assembled audio text string
- **Outputs**: String guaranteed <= 2000 characters, ending at a sentence boundary
- **Edge cases**: Text exactly at limit, text with no sentence boundaries (truncate at word boundary)

### FR-6: Wire into pipeline
- **What**: In `_run_pipeline()`, replace `translation_result.translated_text` in the `generate_and_deliver_audio()` call with `_format_audio_text()` output. Also use cleaned text as `fallback_text` in `send_audio_message_with_fallback()`
- **Inputs**: Pipeline results (prescription_data, translation_result, session.language_name)
- **Outputs**: TTS receives cleaned audio text instead of raw translated text
- **Edge cases**: None — straightforward wiring

---

## Tangible Outcomes

- [ ] **Outcome 1**: `_format_audio_text()` is importable and callable with the correct signature
- [ ] **Outcome 2**: Output contains no emoji characters
- [ ] **Outcome 3**: Output contains no markdown formatting (`*`, `**`, `#`, backticks)
- [ ] **Outcome 4**: Output contains no bullet-point characters (`\u2022`)
- [ ] **Outcome 5**: Medicine names and dosages appear in spoken-friendly sentences
- [ ] **Outcome 6**: Disclaimer is present at the end in spoken-friendly form
- [ ] **Outcome 7**: Output never exceeds 2000 characters
- [ ] **Outcome 8**: `_run_pipeline()` passes `_format_audio_text()` output to `generate_and_deliver_audio()`
- [ ] **Outcome 9**: Empty medicines list produces a valid spoken message (greeting + translated text + disclaimer)
- [ ] **Outcome 10**: No PHI (patient_name, doctor_name) appears in audio text

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_format_audio_text_importable**: `_format_audio_text` exists and is callable
2. **test_format_audio_text_signature**: Accepts (PrescriptionData, TranslationResult, str) and returns str
3. **test_format_audio_text_sync**: Verify it's a regular (sync) function (pure formatting, no I/O)
4. **test_no_emoji_in_output**: Output contains zero emoji characters
5. **test_no_markdown_in_output**: Output contains no `*`, `**`, `#`, or backtick formatting
6. **test_no_bullet_points**: Output contains no `\u2022` bullet characters
7. **test_no_special_unicode**: Output has no warning symbols (`\u26a0`), em-dashes as decorators
8. **test_spoken_greeting**: Output starts with a spoken greeting
9. **test_medicine_name_present**: Each medicine name appears in the output
10. **test_dosage_in_spoken_form**: Dosage appears in a spoken-friendly format (not "Dosage: X")
11. **test_missing_fields_graceful**: Missing optional fields don't produce "None" in output
12. **test_disclaimer_present**: Disclaimer text (cleaned) is present at the end
13. **test_disclaimer_stripped**: Disclaimer emoji/formatting are stripped
14. **test_max_length_2000**: Output with many medicines is <= 2000 characters
15. **test_truncation_ends_sentence**: When truncated, ends at a sentence boundary
16. **test_truncation_fallback_note**: When truncated, includes "read the text message" note
17. **test_empty_medicines**: Empty medicines list produces valid spoken output
18. **test_single_medicine**: Single medicine produces natural speech (no "Next" prefix)
19. **test_no_phi_in_output**: Patient name and doctor name do NOT appear in audio text
20. **test_pipeline_uses_format_audio_text**: `_run_pipeline` passes cleaned text to `generate_and_deliver_audio` (mock-based)

### Mocking Strategy
- No external services needed for FR-1 through FR-5 (pure function)
- FR-6 (pipeline wiring test): mock `_format_audio_text`, `generate_and_deliver_audio`, and all pipeline services
- Build test fixtures with `PrescriptionData` and `TranslationResult` instances

### Coverage Expectation
- All public and private formatting/stripping logic covered
- Edge cases: empty lists, missing fields, truncation boundary, emoji-heavy input, already-clean input

---

## References
- roadmap.md (S10.3 row)
- S10.2 spec (format reply — sibling formatter for WhatsApp text)
- S7.4 spec (simplify_and_translate — upstream provider of TranslationResult)
- S9.1 spec (Bhashini TTS client — downstream consumer of audio text)
- Bhashini TTS practical text length limits
