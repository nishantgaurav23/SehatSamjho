# Architecture & System Design — SehatSamjho

## The Problem (Why This Exists)

9 out of 10 Indian adults have low health literacy. Prescriptions and lab reports
are written in English medical jargon. Most patients speak only their regional language.
India sees ~3 million preventable deaths annually from medical errors — 80% involve
communication failure. At government hospitals, doctors average 2 minutes per patient.
There is no time to explain, and no tool to bridge the gap.

SehatSamjho solves this via WhatsApp: photograph your prescription → get a plain-language
explanation in your language, read aloud. No app install. Works on 2G.

---

## End-to-End Flow

```
PATIENT
  │
  │  Sends prescription photo on WhatsApp
  ▼
TWILIO (WhatsApp Business API)
  │
  │  POST /webhook/whatsapp  (with image URL + phone number)
  ▼
webhooks.py  ←── Redis (reads user session state)
  │
  │  State check: is this user in AWAITING_DOCUMENT state?
  │  Send acknowledgement: "Translating, please wait 20–30 seconds..."
  │  Kick off background processing pipeline
  ▼
extraction.py
  │  GPT-4o Vision API call with image URL
  │  Returns: { medicines: [...], dosages: [...], confidence: "high/low" }
  ▼
drug_lookup.py
  │  For each medicine → Redis cache → CSV → IndianMedicineDB API
  │  Returns: { uses, side_effects, timing, generic_alternative }
  ▼
translation.py
  │  GPT-4o call with extracted JSON + medical glossary context
  │  Returns: plain-language explanation in patient's chosen language
  │  Drug names + dosage numbers preserved in English alongside translation
  ▼
tts.py
  │  Bhashini TTS API call with translated text + language code
  │  Returns: base64 audio → compressed to <500KB → uploaded to S3
  ▼
whatsapp.py
  │  Twilio REST API: send text card + voice message to patient
  ▼
db/models.py
  │  Log metadata to PostgreSQL:
  │  timestamp, language, doc_type, latency_ms, confidence_avg
  │  (NO patient content stored — zero PHI)
  ▼
Redis → reset user session state to IDLE
```

---

## WhatsApp State Machine

Every user has a session stored in Redis. The session holds:
- `state`: which step they're on
- `language`: which language they selected
- `last_activity`: timestamp (session expires after 30 min)

```
┌──────────────────────────────────────────────────────────┐
│                    State Machine                         │
│                                                          │
│  User sends "Hi" or any text                             │
│         │                                                │
│         ▼                                                │
│      IDLE ──────────────────────────────────────────▶   │
│         │  Bot sends language selection buttons          │
│         │  (Hindi / Tamil / Telugu / Kannada / More...)  │
│         ▼                                                │
│  AWAITING_LANGUAGE                                       │
│         │  User taps a language button                   │
│         │  Bot: "Please send a photo of your document"   │
│         ▼                                                │
│  AWAITING_DOCUMENT                                       │
│         │  User sends an image                           │
│         │  Bot: "Translating, please wait 20–30 sec..."  │
│         ▼                                                │
│     PROCESSING  (background async task)                  │
│         │  extract → translate → TTS → send response     │
│         ▼                                                │
│      IDLE  (reset)                                       │
│                                                          │
│  ── Error paths ──────────────────────────────────────── │
│  AWAITING_DOCUMENT + user sends text:                    │
│    "Please send a photo of your document"                │
│  AWAITING_DOCUMENT + blurry image:                       │
│    "We couldn't read this. Try better lighting."         │
│  Any state + non-medical image:                          │
│    "This doesn't appear to be a medical document."       │
│  Any state + 30 min inactivity:                          │
│    Session expires, resets to IDLE                       │
└──────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Why Chosen |
|-------|-----------|------------|
| **Messaging** | WhatsApp via Twilio | 400M+ Indian users. Works on 2G. Supports image + audio natively. No app install. |
| **Backend** | Python / FastAPI | Async-friendly. Strong ML/AI ecosystem. Fast to iterate. |
| **OCR + Extraction** | GPT-4o Vision | Single API call handles printed prescriptions, discharge summaries, lab reports. AIIMS study validated 98.6% accuracy on medical Hindi translation. |
| **Simplification + Translation** | GPT-4o LLM | Same model, chained call. Avoids multi-model orchestration complexity. |
| **Translation Fallback** | IndicTrans2 (AI4Bharat) | Open-source, 22 languages, self-hostable. Used as cross-check when GPT-4o quality is low for specific languages. |
| **Drug Database** | IndianMedicineDB API + Redis cache | 400K+ Indian medicines. Cached locally for <100ms lookups. |
| **Text-to-Speech** | Bhashini TTS | Government-backed, free, all 22 scheduled Indian languages, natural voices. |
| **Database** | PostgreSQL | Metadata and analytics only. Zero patient content. |
| **Session State** | Redis | User conversation state between webhook calls. Drug cache. |
| **Audio Storage** | AWS S3 | Presigned URLs for Twilio audio delivery. Auto-expires. |
| **Hosting** | AWS ECS (ap-south-1 Mumbai) | Data residency in India for DPDP Act 2023 compliance. |
| **CI/CD** | GitHub Actions | Auto-deploy on merge to main. |
| **Analytics** | PostHog | Translation funnels, language distribution, error rates. |

---

## Data Flow & Privacy

```
Image received via WhatsApp
      │
      ▼  (HTTPS, encrypted in transit)
GPT-4o Vision: extract text from image
      │
      ▼  (JSON payload only — image URL not stored)
GPT-4o LLM: simplify + translate extracted text
      │
      ▼
Drug DB lookup: match medicine names (Redis/CSV/API)
      │
      ▼
Bhashini TTS: text → audio
      │
      ▼
S3: store audio with presigned URL (auto-expires in 1 hour)
      │
      ▼
Twilio: deliver text + audio to patient
      │
      ▼
PostgreSQL: log ONLY metadata
  - timestamp
  - language selected
  - document type (prescription / lab report / discharge summary)
  - confidence score average
  - processing time in ms
  - success / error
  NO patient name, NO medicine names, NO image, NO PHI
      │
      ▼
Original image purged from memory after processing
```

**Privacy-by-design principles:**
- Images are processed in-memory and never written to disk or database
- Maximum 24-hour retention only if flagged for manual quality review, then purged
- Consent message sent on first interaction: *"By sending your document, you consent to AI-powered translation. We do not store your medical data."*
- All infrastructure in AWS Mumbai (ap-south-1) for DPDP Act 2023 data residency
- TLS 1.3 in transit, AES-256 at rest

---

## Prompt Engineering Strategy (Two Chained GPT-4o Calls)

### Call 1 — Extraction (Vision)
Takes the image. Returns structured JSON.
Low-confidence fields are flagged rather than guessed.
These show up as ⚠️ warnings in the patient's response.

### Call 2 — Simplification + Translation
Takes the JSON from Call 1 + the patient's chosen language.
Medical glossary is injected as additional context to improve
consistency across translations.

Key rules enforced in the prompt:
- Explain what each medicine does in one simple sentence
- Convert medical terms to everyday words ("hypertension" → "high blood pressure" → vernacular equivalent)
- Preserve drug names, dosage numbers, and frequencies in original English
- Never add medical advice not in the original document
- Never interpret lab values as good or bad — state the value, what it measures, normal range
- Keep total output under 300 words
- Tone: warm, respectful, clear — "as if a trusted family member who understands medicine is reading this to you"

---

## Cost Per Translation

| Item | Cost |
|------|------|
| GPT-4o Vision (extraction) | ~₹2.5 |
| GPT-4o LLM (simplification + translation) | ~₹2.0 |
| Bhashini TTS | Free |
| WhatsApp message fee | ~₹0.5 |
| AWS hosting (amortized) | ~₹0.5 |
| **Total per document** | **~₹5 (~$0.06)** |

At 10,000 documents/month → ₹55,000/month (~$650)

---

## Supported Languages (Target)

| Language | Code | Priority |
|----------|------|----------|
| Hindi | hi | Day 1 — primary |
| Tamil | ta | Day 2 |
| Telugu | te | Day 2 |
| Bengali | bn | Day 2 |
| Kannada | kn | Day 4 |
| Marathi | mr | Day 4 |
| Gujarati | gu | Day 4 |
| Malayalam | ml | Day 4 |
| + 14 more | ... | Post-prototype |

---

## Future Expansion

- **ABDM/ABHA integration** — pull patient health records directly with consent
- **Kiosk mode** — tablet UI for pharmacy dispensing counters
- **EMR webhooks** — auto-translate discharge summaries at point of generation (HealthPlix, Bahmni)
- **IndicTrans2 self-hosted** — full offline fallback for all 22 languages
- **B2B dashboard** — React app for hospital + pharmacy partners
