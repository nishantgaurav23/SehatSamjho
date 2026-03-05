# Spec S13.1 — Hindi End-to-End Smoke Test

## Overview
Send a real printed prescription image via WhatsApp to the deployed SehatSamjho bot. Walk through the full conversation flow in Hindi: language selection, image upload, extraction, translation, and audio delivery. Verify that every stage produces correct, patient-friendly output. This is a manual QA test against the live EC2 deployment.

## Dependencies
- S12.7 (Twilio webhook URL update) — live deployment must be reachable via WhatsApp

## Target Location
Manual test (WhatsApp + server logs)

---

## Functional Requirements

### FR-1: Initiate conversation and receive welcome message
- **What**: Send any message to the Twilio WhatsApp sandbox number
- **Expected**: Bot replies with welcome/consent message followed by language selection buttons (top 8 languages + "More")
- **Verify**: Message arrives within 5 seconds, language list is readable

### FR-2: Select Hindi and receive image prompt
- **What**: Reply with "1" (or "Hindi" or "hi") to select Hindi
- **Expected**: Bot confirms Hindi selection and sends "Please send a photo of your prescription" prompt
- **Verify**: Session state transitions to WAITING_FOR_IMAGE

### FR-3: Send prescription image and receive acknowledgement
- **What**: Send a photo of a real printed prescription (clear, well-lit)
- **Expected**: Bot sends "Translating your document, please wait 20-30 seconds..." acknowledgement immediately
- **Verify**: Acknowledgement arrives within 3 seconds of image send

### FR-4: Receive translated text reply in Hindi
- **What**: After processing, bot sends the translated prescription summary
- **Expected**:
  - Greeting line in Hindi
  - Per-medicine cards with: medicine name (English), purpose (Hindi), dosage instructions (Hindi)
  - Low-confidence items flagged with warning symbol
  - Disclaimer at the end
  - Text is plain-language Hindi (not transliterated English, not medical jargon)
- **Verify**: Message length <= 1600 chars, content is understandable by a non-medical Hindi speaker

### FR-5: Receive audio message in Hindi
- **What**: Bot sends a WhatsApp audio/voice message with the spoken Hindi summary
- **Expected**:
  - Audio plays correctly in WhatsApp
  - Voice is female (Bhashini default)
  - Content matches the text summary (simplified for speech, no emoji/markdown)
  - Audio duration is reasonable (15-60 seconds for a typical prescription)
- **Verify**: Audio is audible, pronunciation is natural Hindi

### FR-6: Verify extraction accuracy
- **What**: Compare GPT-4O Vision extraction output (from server logs) against the actual prescription
- **Expected**:
  - All medicine names correctly identified
  - Dosages match the prescription
  - Doctor name, patient info (if present) correctly extracted
  - Confidence scores are reasonable (>0.7 for clear fields)
- **Verify**: Cross-reference server logs (request_id) with prescription content

### FR-7: Verify drug lookup enrichment
- **What**: Check server logs for drug lookup results
- **Expected**:
  - Common Indian medicines found in Redis cache (from medicines.csv)
  - Drug purpose, side effects, timing instructions populated
  - Unknown medicines gracefully handled (None, not error)
- **Verify**: Check logs for drug lookup hits/misses

### FR-8: Verify interaction log (no PHI)
- **What**: Query the interaction_log table on RDS
- **Expected**:
  - One row created with: phone_hash (SHA-256, not raw number), language_code="hi", doc_type, confidence_avg, latency_ms, status="success"
  - No raw phone number, no image content, no extracted text stored
- **Verify**: `SELECT * FROM interaction_log ORDER BY created_at DESC LIMIT 1;`

### FR-9: Verify session cleanup
- **What**: After pipeline completes, Redis session should be cleaned up
- **Expected**: Session key `session:{phone_hash}` deleted from Redis
- **Verify**: Check Redis via Upstash console or CLI

---

## Tangible Outcomes

- [ ] **Outcome 1**: Welcome message + language buttons received on WhatsApp
- [ ] **Outcome 2**: Hindi selection acknowledged, image prompt received
- [ ] **Outcome 3**: Processing acknowledgement received within 3 seconds
- [ ] **Outcome 4**: Hindi translated text reply received with medicine cards + disclaimer
- [ ] **Outcome 5**: Hindi audio message received and plays correctly
- [ ] **Outcome 6**: Extraction accuracy verified against prescription (>=80% field match)
- [ ] **Outcome 7**: Drug lookup enrichment confirmed in logs
- [ ] **Outcome 8**: interaction_log row has correct fields, zero PHI
- [ ] **Outcome 9**: Redis session cleaned up after completion
- [ ] **Outcome 10**: Full pipeline latency < 30 seconds (image send to audio reply)

---

## Test Procedure

### Prerequisites
1. EC2 instance running with `docker compose -f docker-compose.prod.yml up -d`
2. Twilio WhatsApp sandbox connected to `http://{EC2_IP}/webhook/whatsapp`
3. All environment variables set (OpenAI, Anthropic, Bhashini, Twilio, S3, RDS, Redis)
4. Migrations run (`alembic upgrade head`) and data seeded (`python backend/scripts/seed.py`)
5. A real printed prescription image (clear, well-lit, from an Indian doctor)

### Steps
1. Open WhatsApp, send "Hi" to the Twilio sandbox number
2. Observe welcome message + language buttons (FR-1)
3. Reply "1" to select Hindi (FR-2)
4. Send prescription photo (FR-3)
5. Wait for translated text reply (FR-4)
6. Wait for audio message (FR-5)
7. SSH to EC2, check application logs for extraction output (FR-6)
8. Check logs for drug lookup results (FR-7)
9. Connect to RDS, query interaction_log (FR-8)
10. Check Upstash Redis for session cleanup (FR-9)
11. Note total time from image send to audio received (latency)

### Pass Criteria
- All 10 tangible outcomes checked
- No errors in server logs (warnings OK for non-critical paths)
- Patient-facing output is readable, accurate Hindi

---

## References
- roadmap.md (Phase 13 — QA & Handover)
- S12.7 spec (Twilio webhook setup)
- S10.1-S10.5 specs (pipeline integration)
