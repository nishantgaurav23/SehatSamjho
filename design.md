# Design — SehatSamjho: AI Medical Document Translator

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐
│   Patient    │────▶│  WhatsApp    │────▶│   Backend API   │────▶│  Response     │
│  (WhatsApp)  │◀────│  Business    │◀────│   (FastAPI)     │◀────│  Builder      │
│              │     │  API / Twilio│     │                 │     │              │
└─────────────┘     └──────────────┘     └────────┬────────┘     └──────────────┘
                                                  │
                                    ┌─────────────┼─────────────┐
                                    ▼             ▼             ▼
                              ┌──────────┐ ┌──────────┐ ┌──────────────┐
                              │ GPT-4o   │ │ Drug DB  │ │ Bhashini TTS │
                              │ Vision + │ │ Lookup   │ │ (22 langs)   │
                              │ LLM      │ │ (Redis)  │ │              │
                              └──────────┘ └──────────┘ └──────────────┘

                              ┌──────────┐              ┌──────────────┐
                              │ Indic    │              │ PostgreSQL   │
                              │ Trans2   │              │ (metadata    │
                              │ (fallback)│              │  + analytics)│
                              └──────────┘              └──────────────┘

                                                        ┌──────────────┐
                              ┌─ ─ ─ ─ ─ ┐              │ B2B          │
                              │ ABDM HIU  │              │ Dashboard    │
                              │ (future)  │              │ (React)      │
                              └ ─ ─ ─ ─ ─┘              └──────────────┘
```

## User Flow — Prescription Translation via WhatsApp

1. Patient sends "Hi" → Bot responds with language selection as WhatsApp quick-reply buttons (Hindi / Tamil / Telugu / Kannada / Bengali / More...)
2. Patient taps language → Bot asks to send a photo of their prescription or report
3. Patient sends photo → Bot acknowledges: "Translating your prescription, please wait 20–30 seconds..."
4. System extracts text, simplifies, translates, looks up medicines, generates audio
5. Bot sends back:
   - Text card with translated summary (medicine name → purpose → dosage in plain language)
   - Audio voice message reading the summary aloud
   - Footer disclaimer: "This is a simplified translation. Always follow your doctor's advice."
6. If any extraction has low confidence → Bot flags: "We could not clearly read [item]. Please confirm with your pharmacist."

### Edge Cases

- Blurry or unreadable image → "We couldn't read this clearly. Please try again with better lighting or ask your pharmacist for a printed copy."
- Non-medical document → "This doesn't appear to be a medical document. Please send a prescription, lab report, or discharge summary."
- Language not yet optimized → System uses IndicTrans2 as primary translator and flags: "Translation quality for [language] is still being improved. Please verify important details with your doctor."
- Multiple prescriptions in one image → System detects and processes each separately, returning a combined summary.

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Messaging** | WhatsApp Business API (via Twilio or AiSensy) | 400M+ Indian users, no app install, works on 2G, supports image + audio |
| **Backend** | Python / FastAPI | Async-friendly, strong ML ecosystem, fast iteration |
| **Hosting** | AWS (Mumbai region) or Railway | Data residency in India for DPDP compliance. Mumbai region minimizes latency |
| **OCR + Extraction** | GPT-4o Vision API | Handles printed prescriptions, discharge summaries, lab reports in a single call. AIIMS study validated 98.6% accuracy on medical Hindi translation |
| **Medical Simplification** | GPT-4o (prompted, chained call) | Same model for extraction → simplification → translation. Avoids multi-model orchestration complexity |
| **Translation Fallback** | IndicTrans2 (AI4Bharat) | Open-source, 22 languages, self-hostable. Fallback when GPT-4o translation quality is suboptimal for a specific language. Also used as a cross-check layer |
| **Drug Database** | IndianMedicineDatabase.com API + local Redis cache | 400K+ Indian medicines with compositions, uses, side effects. Cached locally for sub-100ms lookups |
| **Text-to-Speech** | Bhashini TTS APIs | Government-backed, free, all 22 scheduled Indian languages, natural-sounding voices |
| **Database** | PostgreSQL (Supabase or AWS RDS) | Metadata and analytics only. No patient document content stored permanently |
| **Analytics** | PostHog | Usage funnels, error rates, language distribution, retention tracking |
| **B2B Dashboard** | React + Chart.js | Partner-facing dashboard for hospitals and pharmacy chains |

## Data Flow & Privacy Architecture

```
Image received via WhatsApp
      │
      ▼
┌──────────────────────────────────┐
│ 1. Image sent to GPT-4o Vision   │
│    for extraction                │
│    (encrypted in transit, HTTPS) │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ 2. Extracted text sent to GPT-4o │
│    for simplification +          │
│    translation into target       │
│    language                      │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ 3. Medicine names matched        │
│    against drug DB (Redis cache) │
│    for context enrichment        │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ 4. Translated text sent to       │
│    Bhashini TTS → audio file     │
│    generated and compressed      │
│    (< 500KB)                     │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ 5. Text + audio delivered to     │
│    patient via WhatsApp          │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│ 6. Original image purged from    │
│    memory after processing.      │
│    Only metadata logged:         │
│    timestamp, language, doc type,│
│    confidence scores, latency.   │
│    No PHI retained.              │
└──────────────────────────────────┘
```

**Privacy-by-design principles:**

- Patient images are processed in-memory and never written to persistent storage. Purged immediately after response delivery, with a maximum 24-hour retention window only if flagged for manual quality review.
- No personally identifiable health information (PHI) is stored in the database. Metadata logged: timestamp, language selected, document type, confidence score, processing time.
- Consent is collected at first interaction: "By sending your document, you consent to AI-powered translation. We do not store your medical data."
- All infrastructure hosted in India (AWS Mumbai or equivalent) for data residency compliance.
- Encryption: TLS 1.3 in transit, AES-256 at rest for any temporary storage.

## Prompt Engineering Strategy

The core intelligence lives in two chained GPT-4o calls:

**Call 1 — Extraction (Vision)**
```
System: You are a medical document reader specializing in Indian
prescriptions and medical reports. Extract ALL of the following
from the image:
- Patient name (if visible)
- Doctor name and specialization (if visible)
- Each medicine: name, dosage, frequency, duration
- Diagnosis or clinical notes
- Lab values with reference ranges (if lab report)
- Any warnings or special instructions

Output as structured JSON. If any field is unclear or illegible,
set confidence: "low" for that field and include your best guess
in a separate "guess" field. Never present uncertain dosage values
as definitive.
```

**Call 2 — Simplification + Translation**
```
System: You are a caring health educator explaining medical
information to a patient in {language}. The patient has no medical
background and may have limited reading ability.

Rules:
- Explain what each medicine does in one simple sentence
- Convert medical terms to everyday words
  (e.g., "hypertension" → "high blood pressure" →
  "{vernacular equivalent with context}")
- For dosages, use clear simple language
  ("1 tablet, morning, after food")
- Preserve drug names, dosage numbers, and frequencies in
  original English alongside the translation
- NEVER add medical advice not present in the original document
- NEVER interpret lab values as good or bad — state the value,
  what it measures, and the normal range
- Flag anything marked low-confidence from extraction
- Keep total output under 300 words

Tone: Warm, respectful, clear. As if a trusted family member
who happens to understand medicine is reading the document to you.
```

## Safety Design

| Risk | Mitigation |
|------|-----------|
| Wrong dosage extracted from blurry image | Confidence scoring on every extracted field. Low-confidence dosages displayed with ⚠️ warning and "Please confirm with your pharmacist." Audio output emphasizes the uncertainty verbally |
| Translation error changes medical meaning | Critical terms (drug names, dosage numbers, frequency) preserved in original English alongside translation. Never translated phonetically — only explained contextually. IndicTrans2 cross-check flags divergent translations for review |
| Patient treats output as medical advice | Every response includes disclaimer in text and audio. Product language consistently uses "your doctor has prescribed" framing, never "you should take" |
| Drug interaction or contraindication missed | Drug DB lookup surfaces known major side effects and interactions as informational context. System explicitly states it does NOT perform comprehensive interaction checking and advises consulting a pharmacist |
| Patient sends sensitive non-medical content | Auto-detection: if non-medical content detected, respond with "This doesn't appear to be a medical document" and discard without processing |

## Medical Glossary System

A core differentiator is the continuously curated medical glossary — a per-language mapping of medical terms to validated vernacular explanations.

- Initial glossary covers the 500 most common diagnoses, 1,000 most prescribed medicines, and 200 most common lab tests in Indian hospitals.
- Each entry is reviewed by a bilingual medical professional fluent in the target language.
- The glossary is used as a grounding context injected into the GPT-4o translation prompt, improving consistency and accuracy over pure LLM generation.
- Over time, processed documents expand the glossary — new terms encountered in real documents are flagged for human review and addition.
- This glossary becomes a compounding data moat: the more documents processed, the more accurate and comprehensive translations become across every language.

## Future Expansion

The WhatsApp-first architecture is designed to extend into deeper integrations as institutional partnerships grow: ABDM/ABHA integration for pulling patient health records directly with consent, tablet-based kiosk mode for pharmacy dispensing counters and hospital discharge desks, and EMR/HIS system webhooks (HealthPlix, Bahmni) for auto-translating discharge summaries at the point of generation. These channels serve the same paying customers through tighter workflow integration.

## Cost Structure

| Item | Per-document cost | At 10,000 docs/month |
|------|-------------------|----------------------|
| GPT-4o Vision (extraction) | ~₹2.5 ($0.03) | ₹25,000 |
| GPT-4o (simplification + translation) | ~₹2.0 ($0.025) | ₹20,000 |
| Drug DB lookup | Negligible (cached) | — |
| Bhashini TTS | Free | — |
| WhatsApp Business API (message fees) | ~₹0.5 per conversation | ₹5,000 |
| Hosting (AWS Mumbai) | — | ₹5,000 |
| **Total** | **~₹5 per document** | **₹55,000 (~$650)** |

