<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue?logo=python&logoColor=white" alt="Python 3.11"/>
  <img src="https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/tests-1467_passing-brightgreen?logo=pytest&logoColor=white" alt="Tests"/>
  <img src="https://img.shields.io/badge/languages-23_Indian-orange" alt="Languages"/>
  <img src="https://img.shields.io/badge/PHI-zero_stored-critical" alt="Zero PHI"/>
  <img src="https://img.shields.io/badge/AWS-free_tier-FF9900?logo=amazonaws&logoColor=white" alt="AWS Free Tier"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License"/>
</p>

# SehatSamjho

**AI-Powered Prescription Translator — Plain Language + Audio in 23 Indian Languages via WhatsApp & Web**

> Transforming Healthcare Access for 1.4 Billion Indians

Patients photograph their prescriptions on WhatsApp or upload them on the web — and receive a plain-language explanation with audio in any of 23 Indian languages. No app downloads, no signup, no literacy required — just send a photo and listen.

---

## The Problem

> **60% of Indian patients cannot read their own prescriptions.** Language barriers, medical jargon, and illegible handwriting lead to medication errors, missed doses, and preventable harm — especially in rural areas where doctor visits are infrequent.

| Challenge | Description |
|-----------|-------------|
| **Language Barriers** | Prescriptions written in English, patients speak 22+ languages |
| **Medical Jargon** | BD, TDS, SOS — abbreviations patients don't understand |
| **Illegible Handwriting** | Doctor's handwriting often impossible to read |

**Dangerous Consequences:** Medication errors, missed doses, preventable harm — especially in rural areas where doctor visits are infrequent.

## The Solution

SehatSamjho turns any computer or WhatsApp-connected phone into a personal prescription translator.

```
Patient photographs prescription
    -> AI extracts every medicine, dosage, and instruction (GPT-4O Vision)
    -> 1,001-medicine database adds purpose, side effects, interactions
    -> Medical glossary grounds terminology in patient's language
    -> AI simplifies into plain language the patient understands (Claude Sonnet 4.6)
    -> Text-to-speech generates an audio explanation (Edge TTS)
    -> Patient receives text + audio on WhatsApp or Web
```

| Metric | Value |
|--------|-------|
| Total Pipeline Time | ~30-60 seconds |
| Languages Supported | 23 |
| Medicines in Database | 1,001 |
| Tests Passing | 1,467 (100% pass rate) |
| Test-to-Code Ratio | 4.86:1 |

---

## Web Interface — Live Demo

The web platform is fully operational with drag-and-drop upload, 23-language support, structured medicine cards, and an inline audio player.

### Step 1: Choose Language

Select from all 23 scheduled Indian languages with a searchable grid.

<p align="center">
  <img src="docs/screenshots/01-language-selection.png" alt="Language Selection" width="400"/>
</p>

### Step 2: Upload Document

Upload your prescription, lab report, or test result — drag-and-drop or browse. The entire UI is translated to your selected language.

<p align="center">
  <img src="docs/screenshots/02-upload-document.png" alt="Upload Document" width="400"/>
</p>

### Processing

The pipeline reads your document, looks up drug information, translates to your language, and generates audio — all in 30-60 seconds.

<p align="center">
  <img src="docs/screenshots/03-processing.png" alt="Processing" width="400"/>
</p>

### Step 3: View Results

Structured results with three cards — **Your Medicines** (names, dosages), **Why These Medicines** (purpose and side effects), and **Next Steps** (timing and instructions). Includes an inline audio player and confidence scoring.

<p align="center">
  <img src="docs/screenshots/04-results.png" alt="Results" width="700"/>
</p>

---

## How It Works — End-to-End Pipeline

From photo to plain-language explanation in ~30-60 seconds:

| Step | Action | Technology |
|------|--------|------------|
| **1. Capture** | Patient photographs prescription using phone camera | Photo Input |
| **2. Extract** | Structure data with confidence scoring | GPT-4O Vision |
| **3. Enrich** | 1,001-medicine database adds context and details | Drug DB + Redis Cache |
| **4. Translate** | Medical RAG + plain-language simplification | Claude Sonnet 4.6 |
| **5. Deliver** | Text + Audio via WhatsApp or Web interface | Edge TTS |

### Processing Pipeline

```mermaid
flowchart LR
    A["Prescription\nPhoto"]:::input
    B["GPT-4O Vision\nExtract structured data"]:::openai
    C["Drug Lookup\nRedis -> CSV -> API"]:::data
    D["Glossary RAG\nMedical term grounding"]:::data
    E["Claude Sonnet 4.6\nSimplify + Translate"]:::anthropic
    F["Edge TTS\nGenerate audio"]:::tts
    G["S3 Upload\nPresigned URL"]:::storage
    H["WhatsApp / Web Reply\nText + Audio"]:::output

    A --> B --> C --> D --> E --> F --> G --> H

    classDef input fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
    classDef openai fill:#412991,stroke:#2D1B69,stroke-width:2px,color:#fff
    classDef anthropic fill:#D97706,stroke:#92400E,stroke-width:2px,color:#fff
    classDef data fill:#0891B2,stroke:#155E75,stroke-width:2px,color:#fff
    classDef tts fill:#E91E63,stroke:#AD1457,stroke-width:2px,color:#fff
    classDef storage fill:#607D8B,stroke:#37474F,stroke-width:2px,color:#fff
    classDef output fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
```

### WhatsApp User Journey

```
Patient                          SehatSamjho Bot
  |                                    |
  |  [Sends prescription photo]  ----> |
  |                                    |
  | <---- "Select language:"           |
  |        1. Hindi  2. Bengali        |
  |        3. Tamil  4. More...        |
  |                                    |
  |  "1"  ---->                        |
  |                                    |
  | <---- "Hindi selected!"            |
  | <---- [Plain-language explanation]  |
  | <---- [Voice message - 0:25]       |
```

> **500M+ WhatsApp users in India** — meet patients where they already are.

---

## System Architecture

```mermaid
graph TB
    subgraph CLIENT["Patient"]
        WA["WhatsApp"]
        WEB["Web Browser"]
    end

    subgraph GATEWAY["Messaging Gateway"]
        TW["Twilio WhatsApp\nBusiness API"]
    end

    subgraph BACKEND["FastAPI Backend — Python 3.11 Async"]
        direction TB

        subgraph INGRESS["Ingress Layer"]
            WH["POST /webhook/whatsapp"]
            HMAC["HMAC Signature\nVerification"]
            WEBAPI["POST /api/translate"]
            LANDING["GET / Landing Page"]
        end

        subgraph SESSION["Session Layer"]
            SM["Redis State Machine"]
            DISPATCH["Dispatch Router"]
        end

        subgraph PIPELINE["Processing Pipeline"]
            direction LR
            EXT["Extraction\nGPT-4O Vision"]
            DRUG["Drug Enrichment\nRedis -> CSV -> API"]
            GLOSS["Glossary RAG\nRedis Lookup"]
            TRANS["Translation\nClaude Sonnet 4.6"]
            TTS["Text-to-Speech\nEdge TTS"]
        end

        subgraph EGRESS["Egress Layer"]
            FMT["Response Formatter"]
            SEND["WhatsApp / Web Sender"]
        end
    end

    subgraph STORAGE["AWS Services"]
        PG[("RDS PostgreSQL\nMetadata Only")]
        REDIS[("Redis - Upstash\nSessions + Cache")]
        S3[("AWS S3\nAudio Files")]
    end

    subgraph AI["AI Services"]
        OPENAI["OpenAI GPT-4O\nVision"]
        ANTHROPIC["Anthropic Claude\nSonnet 4.6"]
        EDGE["Edge TTS\nOpen-source"]
    end

    WA <-->|"Messages + Media"| TW
    TW -->|"POST webhook"| WH
    WH --> HMAC --> DISPATCH
    WEB -->|"Upload image"| WEBAPI
    WEB -->|"Browse"| LANDING
    WEBAPI --> EXT
    DISPATCH <-->|"Session State"| SM
    SM <-->|"Read/Write"| REDIS

    DISPATCH -->|"Image received"| EXT
    EXT -->|"PrescriptionData"| DRUG
    DRUG -->|"DrugInfo[]"| GLOSS
    GLOSS -->|"Glossary Context"| TRANS
    TRANS -->|"TranslationResult"| TTS
    TTS --> FMT --> SEND
    SEND -->|"Text + Audio"| TW

    EXT <-.->|"Vision API"| OPENAI
    TRANS <-.->|"Messages API"| ANTHROPIC
    TTS <-.->|"TTS Pipeline"| EDGE
    TTS -.->|"Upload audio"| S3
    DISPATCH -.->|"Log metadata"| PG
    DRUG <-.->|"Drug cache"| REDIS
    GLOSS <-.->|"Term cache"| REDIS

    classDef client fill:#E8F5E9,stroke:#2E7D32,stroke-width:2px,color:#1B5E20
    classDef gateway fill:#F3E5F5,stroke:#7B1FA2,stroke-width:2px,color:#4A148C
    classDef backend fill:#E3F2FD,stroke:#1565C0,stroke-width:2px,color:#0D47A1
    classDef storage fill:#ECEFF1,stroke:#546E7A,stroke-width:2px,color:#263238
    classDef ai fill:#FFF3E0,stroke:#E65100,stroke-width:2px,color:#BF360C
    classDef ingress fill:#E1F5FE,stroke:#0277BD,stroke-width:1px,color:#01579B
    classDef session fill:#E8EAF6,stroke:#283593,stroke-width:1px,color:#1A237E
    classDef pipeline fill:#FFF8E1,stroke:#F57F17,stroke-width:1px,color:#F57F17
    classDef egress fill:#E0F2F1,stroke:#00695C,stroke-width:1px,color:#004D40

    class CLIENT client
    class GATEWAY gateway
    class BACKEND backend
    class STORAGE storage
    class AI ai
    class INGRESS ingress
    class SESSION session
    class PIPELINE pipeline
    class EGRESS egress
```

---

## Technology Stack

### AI Layer — Intelligence Core

| Technology | Role |
|-----------|------|
| **GPT-4O Vision** | Prescription image to structured JSON with confidence scoring. Reads handwritten and printed prescriptions. |
| **Claude Sonnet 4.6** | Medical jargon simplification + multilingual translation with RAG |

### Voice Layer — Audio Delivery

| Technology | Role |
|-----------|------|
| **Edge TTS** | Open-source TTS engine for voice synthesis (10 Indian languages, free, no API key) |
| **Audio Pipeline** | Real-time synthesis with S3 storage and 24-hour lifecycle |

### Backend — API & Processing

| Technology | Role |
|-----------|------|
| **FastAPI + Python 3.11** | Fully async high-performance API server (Docker) |
| **Pipeline Orchestrator** | Async, semaphore-controlled, with retry logic |

### Cloud Infrastructure — AWS Services

| Resource | Type | Tier |
|----------|------|------|
| **EC2** | t3.micro (ap-south-1) | Free tier |
| **RDS PostgreSQL** | db.t3.large | Metadata only |
| **S3** | Audio storage | 24-hour lifecycle |
| **Redis (Upstash)** | Session & cache | Free tier |
| **Elastic IP** | Static IP | Free when attached |

---

## Supported Languages

All 23 Indian languages:

| | | | |
|---|---|---|---|
| English | Hindi | Bengali | Tamil |
| Telugu | Marathi | Gujarati | Kannada |
| Malayalam | Odia | Punjabi | Assamese |
| Urdu | Kashmiri | Sindhi | Konkani |
| Maithili | Dogri | Manipuri | Santali |
| Nepali | Bodo | Sanskrit | |

---

## Privacy & Security

| Principle | Implementation |
|-----------|---------------|
| **Zero PHI Storage** | No raw images, prescriptions, or patient data persisted anywhere |
| **Phone Hashing** | Phone numbers SHA-256 hashed before any logging |
| **Metadata-Only Logs** | Only: timestamp, language, doc_type, latency, status, error_code |
| **HMAC Verification** | Every webhook validated via Twilio HMAC signature |
| **Ephemeral Audio** | S3 audio files auto-deleted after 24 hours |
| **No Hardcoded Secrets** | All API keys via `.env` -> pydantic-settings |
| **DISHA-Ready** | Compliant with India's digital health standards |
| **IAM + Elastic IP** | Least privilege access with static IP |

---

## Prototype Status

| Component | Status | Details |
|-----------|--------|---------|
| **Web UI** | Live | Drag-and-drop upload, 23 languages, medicine cards, inline audio player |
| **AI Pipeline** | Live | GPT-4O Vision extraction, Claude translation, Edge TTS — end-to-end tested |
| **Drug Database** | Live | 1,001 medicines, 49 therapeutic classes, Redis-cached, <100ms response |
| **WhatsApp Integration** | In Progress | Twilio webhook handler built, message parsing complete, delivery integration ongoing |
| **Health Endpoint** | Live | `GET /health` — real-time system monitoring |
| **Test Suite** | Live | 1,467 tests, 100% passing, 4.86:1 test-to-code ratio |

---

## Cost Estimate (Prototype)

| Resource | Monthly Cost |
|----------|-------------|
| EC2 t3.micro | $0 (free tier) |
| RDS PostgreSQL | $0 (free tier) |
| S3 audio storage | $0 (free tier) |
| Upstash Redis | $0 (free tier) |
| Edge TTS (Open-source) | $0 (free, no API key) |
| OpenAI GPT-4O Vision | ~$5 / 1,000 documents |
| Claude Sonnet 4.6 | ~$2 / 1,000 documents |
| Twilio WhatsApp | ~$1-5 during testing |
| **Total** | **~$8-15/month** |

---

## What's Next — Future Development

| Feature | Status | Description |
|---------|--------|-------------|
| **Twilio WhatsApp Live** | In Progress | Complete WhatsApp Business API integration |
| **ABDM Integration** | Planned | Connect with Ayushman Bharat Digital Mission for verified digital prescriptions |
| **Lab Report Translation** | Already Done | Blood test results, X-ray reports, discharge summaries |
| **B2B Analytics Dashboard** | Planned | React dashboard for hospitals and pharmacies with usage analytics |
| **Bhashini TTS** | Planned | Government-backed TTS for 22 languages |
| **PDF Extraction** | Planned | Support for PDF document uploads |
| **Multi-page Support** | Planned | Handle multiple prescription pages |
| **Doctor Verification** | Planned | Prescription validation loop |
| **Mobile App** | Planned | Native iOS and Android apps |

---

## Team

| Role | Name |
|------|------|
| **Team Leader** | Nishant Gaurav |
| **Team Name** | SehatSamjho |

Built for the **AWS AI for Bharat Hackathon 2025**.

---

## License

MIT
