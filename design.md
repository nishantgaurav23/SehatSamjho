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
                              │ LLM      │ │ API      │ │              │
                              └──────────┘ └──────────┘ └──────────────┘
```

## User Flow

**Happy path — prescription translation via WhatsApp:**

1. Patient sends "Hi" → Bot responds with language selection menu (Hindi / Tamil / Telugu) as WhatsApp quick-reply buttons
2. Patient taps language → Bot asks to send a photo of their prescription or report
3. Patient sends photo → Bot acknowledges ("Translating your prescription, please wait 20–30 seconds...")
4. System extracts text, simplifies, translates, generates audio
5. Bot sends back:
   - Text card with translated summary (medicine name → purpose → dosage in plain language)
   - Audio message (Bhashini TTS) reading the summary aloud
   - Footer disclaimer: "This is a simplified translation. Always follow your doctor's advice."
6. If any extraction has low confidence → Bot flags: "We could not clearly read [item]. Please confirm with your pharmacist."

**Edge cases handled:**
- Blurry/unreadable image → "We couldn't read this clearly. Please try again with better lighting."
- Non-medical document → "This doesn't appear to be a medical document. Please send a prescription, lab report, or discharge summary."
- Unsupported language request → "We currently support Hindi, Tamil, and Telugu. More languages coming soon."

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Messaging** | WhatsApp Business API (via Twilio or AiSensy) | 400M+ Indian users, no app install, works on 2G, supports image + audio |
| **Backend** | Python / FastAPI on Railway or Render | Fast to build, async-friendly, free tier for prototype |
| **OCR + Extraction** | GPT-4o Vision API | Handles printed prescriptions, discharge summaries, lab reports in a single call. AIIMS study validated 98.6% accuracy on medical Hindi translation |
| **Medical Simplification** | GPT-4o (prompted) | Same model, chained call: extract → simplify → translate. Avoids multi-model orchestration complexity |
| **Drug Database** | IndianMedicineDatabase.com API + local cache | 400K+ Indian medicines with compositions, uses, side effects |
| **Translation fallback** | IndicTrans2 (AI4Bharat) | Open-source, 22 languages, runs locally. Fallback if GPT-4o translation quality drops for a specific language |
| **Text-to-Speech** | Bhashini TTS APIs | Government-backed, free, supports all 22 scheduled Indian languages, natural-sounding voices |
| **Storage** | PostgreSQL (Supabase free tier) | Metadata only (timestamps, language, document type, confidence scores). NO patient document content stored permanently |
| **Monitoring** | PostHog (free tier) | Usage analytics, funnel tracking, error rates |

## Data Flow & Privacy Architecture

```
Image received
      │
      ▼
┌─────────────────────────┐
│ 1. Image sent to GPT-4o │  (encrypted in transit via HTTPS)
│    Vision for extraction │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 2. Extracted text sent   │  (no image stored — processed in memory only)
│    to GPT-4o for         │
│    simplification +      │
│    translation           │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 3. Medicine names        │
│    matched against       │
│    drug DB for context   │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 4. Translated text sent  │
│    to Bhashini TTS →     │
│    audio file generated  │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 5. Text + audio sent     │
│    back to patient via   │
│    WhatsApp              │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ 6. Image deleted from    │
│    memory. Only metadata │
│    logged (no PHI).      │
└─────────────────────────┘
```

**Privacy-by-design principles:**
- Patient images are never written to disk — processed in-memory and discarded
- No personally identifiable health information (PHI) is stored in the database
- Metadata logged: timestamp, language selected, document type (prescription/lab/discharge), confidence score, processing time
- Consent collected at first interaction via WhatsApp message ("By sending your document, you consent to AI-powered translation. We do not store your medical data.")

## Prompt Engineering Strategy

The core intelligence lives in two chained GPT-4o calls:

**Call 1 — Extraction (Vision)**
```
System: You are a medical document reader specializing in Indian prescriptions 
and medical reports. Extract ALL of the following from the image:
- Patient name (if visible)
- Doctor name and specialization (if visible)  
- Each medicine: name, dosage, frequency, duration
- Diagnosis or clinical notes
- Lab values (if lab report)
- Any warnings or special instructions

Output as structured JSON. If any field is unclear or illegible, 
set confidence: "low" for that field. Never guess dosage values — 
mark them uncertain instead.
```

**Call 2 — Simplification + Translation**
```
System: You are a caring health educator explaining medical information 
to a patient in {language}. The patient has no medical background and 
may have limited reading ability.

Rules:
- Explain what each medicine does in one simple sentence
- Convert medical terms to everyday words (e.g., "hypertension" → 
  "high blood pressure" → "{vernacular equivalent}")
- For dosages, use familiar references ("one tablet the size of a 
  small dal" is NOT needed — just "1 tablet, morning, after food")
- NEVER add medical advice not present in the original document
- NEVER interpret lab values as good/bad — just state the value 
  and what it measures
- Flag anything marked as low-confidence from extraction
- Keep the total output under 300 words

Tone: Warm, respectful, clear. As if a trusted family member is 
reading the prescription to you.
```

## Safety Design

| Risk | Mitigation |
|------|-----------|
| Wrong dosage extracted from blurry image | Confidence scoring on extraction. Low-confidence dosages displayed with ⚠️ warning and "Please confirm with your pharmacist" |
| Translation error changes medical meaning | Critical terms (drug names, dosage numbers, frequency) are preserved in original English alongside translation. Never translated phonetically — only explained |
| Patient treats output as medical advice | Every response includes disclaimer. Product never says "you should take" — only "your doctor has prescribed" |
| Allergies or contraindications missed | Drug DB lookup surfaces known major side effects. System adds "Tell your doctor if you experience..." but does NOT perform interaction checking (out of scope for v1) |
| Patient sends sensitive personal information beyond medical docs | Auto-detection prompt: if non-medical content detected, respond with generic "This doesn't appear to be a medical document" and discard |

## MVP Scope — What We Build in 1 Week (Prototype)

| Day | Deliverable |
|-----|------------|
| 1 | Set up WhatsApp Business API sandbox (Twilio/AiSensy). Build basic message handler in FastAPI |
| 2 | Integrate GPT-4o Vision — extraction prompt tuned on 20 sample Indian prescriptions (sourced from research papers + team's own prescriptions) |
| 3 | Build simplification + translation chain. Test on Hindi with 30 sample documents. Integrate drug DB lookup |
| 4 | Integrate Bhashini TTS for Hindi audio. Add Tamil and Telugu translation paths |
| 5 | Safety layer — confidence scoring, disclaimers, edge case handling. Basic error handling |
| 6 | End-to-end testing with 20 real prescriptions across 3 languages. Fix accuracy issues |
| 7 | Demo prep. Record 3 compelling demo videos (one per language). Prepare pitch deck |

**Prototype output:** A working WhatsApp bot that accepts a prescription photo and returns a plain-language translated summary (text + audio) in Hindi, Tamil, or Telugu within 30 seconds.

## 3-Month MVP Roadmap (Post-Hackathon)

**Month 1 — Validate accuracy**
- Partner with 1 hospital (target: government hospital in Chennai or Hyderabad)
- Process 200+ real documents with bilingual medical professional review
- Achieve ≥95% accuracy benchmark
- Add support for discharge summaries and basic lab reports

**Month 2 — Distribution infrastructure**
- Begin ABDM sandbox integration (using Eka Care ABDM Connect middleware)
- Build pharmacy counter integration (tablet-based kiosk for scanning at dispensing)
- Expand to 5 languages (add Kannada, Bengali)

**Month 3 — PMF signals**
- Deploy at 2–3 hospital discharge counters
- Target: 500+ documents processed, ≥80% patient comprehension, ≥30% repeat usage
- Pitch to Apollo Pharmacy, state health missions, and Ayushman Bharat empanelled hospital networks
- Explore insurance company partnerships (translated discharge summaries → better patient compliance → fewer readmissions)

## Cost Estimate (Prototype Phase)

| Item | Monthly Cost |
|------|-------------|
| GPT-4o API (500 documents × ~$0.05 each) | ~$25 |
| WhatsApp Business API (AiSensy starter) | ₹999 (~$12) |
| Bhashini TTS API | Free |
| Hosting (Railway/Render) | Free tier |
| Domain + misc | ~$10 |
| **Total** | **~$50/month** |

Scales to ~$500/month at 5,000 documents — well within seed/grant funding range.
