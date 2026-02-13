# Requirements — SehatSamjho: AI Medical Document Translator

## Problem

9 out of 10 Indian adults have low health literacy. Medical documents — prescriptions, discharge summaries, lab reports — are written in English medical jargon, but most patients speak only their regional language and many cannot read at all. India sees ~3 million preventable deaths annually from medical errors, with communication failure implicated in 80% of serious incidents. At government hospitals, doctors spend an average of 2 minutes per consultation. There is no time to explain, and no tool to bridge the gap.

No product in India currently translates individual patient medical documents into plain-language Indian vernacular. SehatSamjho fills this gap — it takes any medical document, extracts the content, translates it into the patient's language at an 8th-grade reading level, and reads it aloud.

## Target Users

**Primary (Paying Customers):** Patients and caregivers at public and private hospitals — low-literacy, non-English-speaking, spanning Tier 1 through rural India. They access SehatSamjho via WhatsApp, requiring no app download and no ability to read.

**Secondary:** Hospital administrators, pharmacy chains (Apollo, MedPlus), state health missions, and insurance providers who need to improve patient comprehension, treatment compliance, and reduce readmissions. These institutions deploy SehatSamjho for their patients — the patient interacts with the product, the institution pays for it.

## Core Flow

A patient or caregiver photographs their prescription, discharge summary, or lab report and sends it to SehatSamjho via WhatsApp. The system extracts the medical content, converts jargon into a plain-language explanation in the patient's chosen language, looks up each medicine in a drug database for additional context, and reads the full translation aloud as a voice message — all within 30 seconds.

Supported document types: handwritten and printed prescriptions, typed discharge summaries, and pathology/radiology lab reports.

## Core Features

### Document Intake via WhatsApp

- Patients send a photo of their medical document to the SehatSamjho WhatsApp number. Language selection happens through quick-reply buttons — no typing required.
- WhatsApp is the sole primary channel: 400M+ Indian users, works on 2G/3G, supports image and audio natively, and requires no app install or literacy to operate.

### Intelligent Extraction

- GPT-4o Vision extracts structured data from document images: patient name, doctor details, each medicine (name, dosage, frequency, duration), diagnoses, lab values, and special instructions.
- Every extracted field carries a confidence score. Low-confidence items (illegible handwriting, ambiguous abbreviations) are explicitly flagged rather than guessed.

### Medical Simplification & Translation

- Medical jargon is converted into plain-language explanations in the patient's chosen language. All 22 scheduled Indian languages are supported, powered by GPT-4o for primary translation with IndicTrans2 (AI4Bharat) as a fallback and quality cross-check.
- The system explains rather than literally translates — "hypertension" becomes "high blood pressure" becomes the appropriate vernacular phrase with context, not a phonetic transliteration.
- Critical terms (drug names, dosage numbers, frequencies) are preserved in original English alongside the translation so pharmacists and caregivers can cross-reference.

### Audio Playback

- Every translated summary is converted to natural-sounding speech using Bhashini TTS APIs, covering all 22 scheduled languages.
- Audio is delivered as a WhatsApp voice message — the most familiar format for low-literacy users.

### Medicine Intelligence

- Each medicine in the prescription is matched against a comprehensive drug database (IndianMedicineDatabase.com, 400K+ entries) to surface: generic name, therapeutic purpose, common side effects, food/timing instructions, and known major interactions.
- If a prescribed medicine has a widely available generic alternative, the system notes this (informational only, not a substitution recommendation).

### Safety Guardrails

- The system never provides diagnoses, treatment recommendations, or clinical interpretations of lab values. It translates and explains what the doctor wrote — nothing more.
- Dosage values and allergy warnings identified as low-confidence are flagged with explicit warnings and "Please confirm with your pharmacist" callouts.
- Every output includes a disclaimer: "This is a simplified translation of your medical document. Always follow your doctor's advice."
- An audit log tracks every translation for quality review, without storing the original patient document content beyond the processing window.

### B2B Dashboard

- Hospital and pharmacy partners receive a dashboard showing translation volumes, languages served, document types processed, confidence score distributions, and patient satisfaction scores.
- Enables partners to measure the impact of SehatSamjho on patient outcomes and justify continued investment.

## Future Expansion

SehatSamjho's WhatsApp-first architecture is designed to extend into additional channels as adoption grows: ABDM/ABHA integration for pulling patient health records directly with consent, tablet-based kiosk mode for pharmacy dispensing counters and hospital discharge desks, and EMR/HIS system webhooks for auto-translating discharge summaries at the point of generation. These expansions serve the same paying customers (hospitals, pharmacies, insurers) through deeper integration into their existing workflows.

## Functional Requirements

| ID | Requirement |
|----|------------|
| FR-1 | Accept image input via WhatsApp |
| FR-2 | Extract structured data from medical document images (medicines, dosages, frequency, doctor notes, lab values) with per-field confidence scores |
| FR-3 | Translate extracted content into patient-selected language at ≤8th grade reading level |
| FR-4 | Support all 22 scheduled Indian languages |
| FR-5 | Generate audio output of translated summary via Bhashini TTS, delivered as WhatsApp voice message |
| FR-6 | Match medicines to drug database and surface plain-language information (purpose, side effects, timing, interactions) |
| FR-7 | Flag low-confidence extractions with visual and audio indicators |
| FR-8 | Display disclaimers and safety notices on all outputs |
| FR-9 | Provide language selection via WhatsApp quick-reply buttons (no typing required) |
| FR-10 | Support prescriptions, discharge summaries, pathology reports, and radiology reports |
| FR-11 | Provide a B2B dashboard for hospital and pharmacy partners (volumes, languages, satisfaction metrics) |
| FR-12 | Track usage analytics: documents processed, languages used, document types, repeat users, error rates |

## Non-Functional Requirements

- **Accuracy:** ≥95% factual accuracy on medicine names, dosages, and frequencies validated against the source document.
- **Latency:** Full translation + audio delivered within 30 seconds of image upload on a 3G connection.
- **Availability:** 99.5% uptime.
- **Privacy:** No patient document content stored beyond processing window (24 hrs max for quality review, then purged). All data encrypted in transit (TLS 1.3) and at rest (AES-256). DPDP Act 2023 compliant — informed consent, purpose limitation, breach notification readiness.
- **Cost:** LLM API cost per document ≤ ₹5 (~$0.06) to maintain viable unit economics at scale.
- **Accessibility:** Fully usable by patients who cannot read — audio-first design, no text input required beyond initial language selection tap.

## Success Metrics

| Metric | Target |
|--------|--------|
| Translation accuracy (validated by bilingual medical professionals) | ≥95% |
| Patient comprehension (post-use survey) | ≥80% report understanding their document |
| Monthly documents processed | 10,000+ |
| Repeat usage (same user, second document within 30 days) | ≥30% |
| Hospital/pharmacy partner retention (continue after pilot) | ≥70% |
| Languages actively used by patients | ≥8 |

## Constraints

- **Regulatory:** Product is positioned as an informational and health literacy tool, not a medical device. No clinical interpretation, diagnosis, or treatment advice. This positions it outside CDSCO's Software as Medical Device (SaMD) classification.
- **Data privacy:** Full DPDP Act 2023 compliance. Health data processed only with informed consent, used only for translation, and not retained.
- **Infrastructure:** Must function on low-bandwidth connections (2G/3G) common in rural India. WhatsApp-first design ensures minimal data usage. Audio files compressed to under 500KB.
- **Language:** Medical terminology often has no direct vernacular equivalent. The system explains concepts rather than forcing literal translations. A curated medical glossary per language captures validated vernacular phrases for common conditions, updated continuously.

## Key Assumptions

1. GPT-4o Vision extracts text from printed Indian prescriptions with ≥90% accuracy (supported by MIRAGE dataset research). Handwritten prescriptions have lower baseline accuracy and are handled with explicit confidence flagging.
2. GPT-4o achieves ≥95% medical translation accuracy for Indian languages (supported by AIIMS New Delhi study showing 98.6% on radiology → Hindi).
3. Bhashini TTS APIs remain available for startup use at free or nominal cost.
4. Hospitals and pharmacy chains are willing to adopt and pay for a patient literacy tool — precedent exists with Practo (15 vernacular languages for consultations), Eka Care (ABDM integration), and PharmEasy (pharmacy partnerships at scale).
5. Patients and caregivers engage with WhatsApp bots for health information — MyGov Corona Helpdesk handled 100M+ queries, and Khushi Baby's ASHABot onboarded 869 health workers with 24,000+ messages.
