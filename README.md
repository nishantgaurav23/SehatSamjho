<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue?logo=python&logoColor=white" alt="Python 3.11"/>
  <img src="https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/tests-1468_passing-brightgreen?logo=pytest&logoColor=white" alt="Tests"/>
  <img src="https://img.shields.io/badge/languages-22_Indian-orange" alt="Languages"/>
  <img src="https://img.shields.io/badge/PHI-zero_stored-critical" alt="Zero PHI"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License"/>
</p>

# SehatSamjho

**AI-powered medical document translator for WhatsApp and Web.**

Patients photograph their prescriptions on WhatsApp or upload them on the web — and receive a plain-language explanation with audio in any of 22 Indian languages.

---

## The Problem

> 60% of Indian patients cannot read their own prescriptions. Language barriers, medical jargon, and illegible handwriting lead to medication errors, missed doses, and preventable harm — especially in rural areas where doctor visits are infrequent.

## The Solution

SehatSamjho turns any WhatsApp-connected phone into a personal prescription translator. No app downloads, no signup, no literacy required — just send a photo and listen. A web interface is also available for direct browser-based uploads.

```
Patient photographs prescription
    -> AI extracts every medicine, dosage, and instruction
    -> Drug database adds purpose, side effects, interactions
    -> Medical glossary grounds terminology in patient's language
    -> AI simplifies into plain language the patient understands
    -> Text-to-speech generates an audio explanation
    -> Patient receives text + audio on WhatsApp
```

---

## Table of Contents

- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Supported Languages](#supported-languages)
- [Project Structure](#project-structure)
- [How It Works — Step by Step](#how-it-works--step-by-step)
  - [WhatsApp Flow](#1-patient-sends-a-message-whatsapp---twilio---webhook)
  - [Web Upload Flow](#web-upload-flow)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Option A: Local Setup (without Docker)](#option-a-local-setup-without-docker)
  - [Option B: Docker Setup (recommended)](#option-b-docker-setup-recommended)
- [Environment Variables](#environment-variables)
- [Running Tests](#running-tests)
- [Linting](#linting)
- [Deployment to AWS](#deployment-to-aws)
- [Privacy and Security](#privacy-and-security)
- [Development Progress](#development-progress)
- [Cost Estimate](#cost-estimate-prototype)
- [License](#license)

---

## Architecture

### High-Level System Design

```mermaid
graph TB
    subgraph CLIENT["Patient"]
        WA["WhatsApp"]
        WEB["Web Browser"]
    end

    subgraph GATEWAY["Messaging Gateway"]
        TW["Twilio WhatsApp<br/>Business API"]
    end

    subgraph BACKEND["FastAPI Backend — Python 3.11 Async"]
        direction TB

        subgraph INGRESS["Ingress Layer"]
            WH["POST /webhook/whatsapp"]
            HMAC["HMAC Signature<br/>Verification"]
            WEBAPI["POST /api/translate"]
            LANDING["GET / Landing Page"]
        end

        subgraph SESSION["Session Layer"]
            SM["Redis State Machine"]
            DISPATCH["Dispatch Router"]
        end

        subgraph PIPELINE["Processing Pipeline"]
            direction LR
            EXT["Extraction<br/>GPT-4O Vision"]
            DRUG["Drug Enrichment<br/>Redis -> CSV -> API"]
            GLOSS["Glossary RAG<br/>Redis Lookup"]
            TRANS["Translation<br/>Claude Sonnet 4.6"]
            TTS["Text-to-Speech<br/>Bhashini / Edge TTS"]
        end

        subgraph EGRESS["Egress Layer"]
            FMT["Response Formatter"]
            SEND["WhatsApp Sender"]
        end
    end

    subgraph STORAGE["Data Stores"]
        PG[("PostgreSQL<br/>Metadata Only")]
        REDIS[("Redis<br/>Sessions + Cache")]
        S3[("AWS S3<br/>Audio Files")]
    end

    subgraph AI["AI Services"]
        OPENAI["OpenAI GPT-4O<br/>Vision"]
        ANTHROPIC["Anthropic Claude<br/>Sonnet 4.6"]
        BHASHINI["Bhashini TTS<br/>Gov. of India"]
        EDGE["Edge TTS<br/>Microsoft Neural"]
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
    TTS <-.->|"TTS Pipeline"| BHASHINI
    TTS <-.->|"Fallback TTS"| EDGE
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

### Processing Pipeline — Step by Step

```mermaid
flowchart LR
    A["Prescription<br/>Photo"]:::input
    B["GPT-4O Vision<br/><i>Extract structured data</i>"]:::openai
    C["Drug Lookup<br/><i>Redis -> CSV -> API</i>"]:::data
    D["Glossary RAG<br/><i>Medical term grounding</i>"]:::data
    E["Claude Sonnet 4.6<br/><i>Simplify + Translate</i>"]:::anthropic
    F["Bhashini / Edge TTS<br/><i>Generate audio</i>"]:::tts
    G["S3 Upload<br/><i>Presigned URL</i>"]:::storage
    H["WhatsApp Reply<br/><i>Text + Audio</i>"]:::output

    A --> B --> C --> D --> E --> F --> G --> H

    classDef input fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
    classDef openai fill:#412991,stroke:#2D1B69,stroke-width:2px,color:#fff
    classDef anthropic fill:#D97706,stroke:#92400E,stroke-width:2px,color:#fff
    classDef data fill:#0891B2,stroke:#155E75,stroke-width:2px,color:#fff
    classDef tts fill:#E91E63,stroke:#AD1457,stroke-width:2px,color:#fff
    classDef storage fill:#607D8B,stroke:#37474F,stroke-width:2px,color:#fff
    classDef output fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
```

### WhatsApp Conversation Flow

```mermaid
stateDiagram-v2
    [*] --> Welcome: User sends any message
    Welcome --> WaitingForLanguage: Show language menu

    WaitingForLanguage --> WaitingForImage: Valid language selected
    WaitingForLanguage --> WaitingForLanguage: Invalid input -> re-show menu

    WaitingForImage --> Processing: Image received
    WaitingForImage --> WaitingForImage: No image -> prompt again

    Processing --> [*]: Send text + audio reply

    state Processing {
        [*] --> Extract
        Extract --> Enrich
        Enrich --> Translate
        Translate --> TTS
        TTS --> Deliver
        Deliver --> [*]
    }
```

---

## Tech Stack

| Layer | Technology | Role |
|-------|-----------|------|
| **Messaging** | Twilio WhatsApp Business API | Send/receive WhatsApp messages and media |
| **Backend** | Python 3.11 / FastAPI / uvicorn | Fully async request handling |
| **Web Frontend** | Jinja2 templates + vanilla JS | Browser-based prescription upload and translation |
| **Vision AI** | OpenAI GPT-4O (`gpt-4o`) | Extract medicines, dosages, instructions from images |
| **Translation AI** | Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`) | Simplify medical jargon + translate to patient's language |
| **Text-to-Speech** | Bhashini (Gov. of India) + Edge TTS (Microsoft) | Bhashini: 22 languages (needs API key). Edge TTS: 10 languages, free, no key needed (automatic fallback) |
| **Drug Database** | Local CSV (1000+ medicines) + Redis cache + API fallback | Sub-100ms drug lookups with enrichment |
| **Medical Glossary** | Per-language JSON (100 terms x 6 languages) + Redis | RAG context injection for accurate medical terminology |
| **Database** | PostgreSQL (async SQLAlchemy + asyncpg) | Metadata logging only — zero PHI |
| **Cache** | Redis | Session state, drug cache, glossary cache |
| **Audio Storage** | AWS S3 | Presigned URLs, auto-delete after 24 hours |
| **Hosting** | AWS EC2 t3.micro (ap-south-1) | Docker deployment, free tier eligible |
| **Migrations** | Alembic | Async-compatible schema management |

---

## Supported Languages

All 22 scheduled languages of India:

| | | | |
|---|---|---|---|
| Hindi | Bengali | Tamil | Telugu |
| Marathi | Gujarati | Kannada | Malayalam |
| Odia | Punjabi | Assamese | Urdu |
| Kashmiri | Sindhi | Konkani | Maithili |
| Dogri | Manipuri | Santali | Nepali |
| Bodo | Sanskrit | | |

---

## Project Structure

```
SehatSamjho/
├── backend/
│   ├── app/
│   │   ├── main.py                    # App factory, lifespan, /health, GET / landing page
│   │   ├── api/
│   │   │   ├── webhooks.py            # WhatsApp webhook + state machine + pipeline
│   │   │   ├── web.py                 # POST /api/translate — web upload endpoint
│   │   │   └── dashboard.py           # Analytics endpoints (stub)
│   │   ├── core/
│   │   │   ├── config.py              # pydantic-settings (12 env vars)
│   │   │   └── security.py            # Twilio HMAC signature verification
│   │   ├── db/
│   │   │   ├── database.py            # Async SQLAlchemy engine + session factory
│   │   │   ├── redis.py               # Async Redis client + connection pool
│   │   │   └── models.py              # InteractionLog table (metadata, zero PHI)
│   │   ├── models/
│   │   │   └── schemas.py             # 10 Pydantic models (request/response)
│   │   └── services/
│   │       ├── extraction.py          # GPT-4O Vision -> PrescriptionData
│   │       ├── translation.py         # Claude Sonnet 4.6 -> TranslationResult
│   │       ├── tts.py                 # Bhashini/Edge TTS -> S3 audio -> presigned URL
│   │       ├── tts_edge.py            # Edge TTS fallback (free, no API key)
│   │       ├── drug_lookup.py         # Redis/CSV/API -> DrugInfo enrichment
│   │       ├── glossary.py            # Medical glossary loader + Redis RAG
│   │       └── whatsapp.py            # Language data + Twilio messaging helpers
│   ├── static/                        # CSS + JS for web frontend
│   ├── templates/                     # Jinja2 HTML templates
│   ├── scripts/
│   │   └── seed.py                    # Load drugs + glossary into Redis
│   ├── alembic/                       # Database migrations
│   ├── tests/                         # 1468+ tests, 100% mocked externals
│   └── Dockerfile                     # Multi-stage (base/dev/prod)
├── data/
│   ├── drugs/medicines.csv            # 1001 Indian medicines
│   └── glossary/{hi,ta,te,kn,bn,mr}.json  # 100 terms x 6 languages
├── scripts/
│   ├── deploy.sh                      # EC2 deployment script
│   ├── ec2-setup.sh                   # EC2 instance provisioning
│   ├── rds-setup.sh                   # RDS PostgreSQL provisioning
│   ├── setup-s3.sh                    # S3 bucket setup
│   ├── setup-iam.sh                   # IAM role for EC2
│   └── verify_webhook.sh             # Twilio webhook verification
├── specs/                             # Spec-driven development (69 specs)
├── docker-compose.yml                 # Local dev (app + postgres + redis)
├── docker-compose.prod.yml            # Production overrides
├── pyproject.toml                     # Single source of truth for deps
├── Makefile                           # 11 developer commands
├── roadmap.md                         # Full project roadmap + spec index
└── .env.example                       # All 12 required env vars
```

---

## How It Works — Step by Step

This section walks through the complete flow from a patient sending a WhatsApp message to receiving their translated prescription.

### 1. Patient Sends a Message (WhatsApp -> Twilio -> Webhook)

A patient messages the SehatSamjho WhatsApp number. Twilio receives the message and sends an HTTP POST to our webhook endpoint.

**Entry point:** `backend/app/api/webhooks.py` -> `webhook_whatsapp()`

```
Twilio POST /webhook/whatsapp
  -> HMAC signature validation (core/security.py)
  -> Parse form body into WebhookPayload (Pydantic model)
  -> Generate unique request_id (UUID4) for log correlation
  -> Dispatch to handler based on session state
```

### 2. Session State Machine (Redis)

The conversation follows a state machine stored in Redis (key: `session:{phone_number}`, TTL: 30 minutes).

**File:** `backend/app/api/webhooks.py` -> `_dispatch()`

| State | What Happens | Next State |
|-------|-------------|------------|
| **No session** | Send welcome message + language menu | `WAITING_FOR_LANGUAGE` |
| `WAITING_FOR_LANGUAGE` | Parse language selection (number, code, or name) | `WAITING_FOR_IMAGE` |
| `WAITING_FOR_IMAGE` | Validate image attachment, send "processing" ack | `PROCESSING` |
| `PROCESSING` | Run the full pipeline (steps 3-8 below) | Session deleted |

### 3. Prescription Extraction (GPT-4O Vision)

When a valid image is received, the pipeline starts.

**File:** `backend/app/services/extraction.py` -> `extract_prescription()`

```
Download image from Twilio URL (httpx async)
  -> Base64 encode
  -> Send to OpenAI GPT-4O Vision with structured extraction prompt
  -> Parse JSON response into PrescriptionData (Pydantic model)
  -> Each medicine has: name, dosage, frequency, duration, confidence score
```

Custom exceptions for semantic errors:
- `NotMedicalDocumentError` — image is not a prescription/medical document
- `ImageNotReadableError` — image is too blurry or illegible
- Transient OpenAI API errors are retried (3 attempts, exponential backoff via Tenacity)

### 4. Drug Enrichment (Redis -> CSV -> API)

Each extracted medicine is looked up for additional context.

**File:** `backend/app/services/drug_lookup.py` -> `enrich_prescription()`

```
For each medicine in PrescriptionData (concurrent via asyncio.gather):
  -> Check Redis cache (hash key: drugs:{normalized_name})
  -> Cache miss -> search local CSV (1001 Indian medicines)
  -> CSV miss -> call IndianMedicineDB API (with retry)
  -> Returns DrugInfo: purpose, side effects, timing, interactions
```

The drug database (`data/drugs/medicines.csv`) contains 1001 commonly prescribed Indian medicines across 49 therapeutic classes.

### 5. Medical Glossary Lookup (Redis RAG)

Medical terms from the prescription are matched against a per-language glossary.

**File:** `backend/app/services/glossary.py` -> `lookup_terms()` + `format_glossary_context()`

```
Extract medicine names from PrescriptionData
  -> Redis HMGET on glossary:{language_code} hash
  -> Match terms to plain-language explanations in patient's language
  -> Format as structured context block for Claude translation prompt
```

Glossary data covers 6 languages (Hindi, Tamil, Telugu, Kannada, Bengali, Marathi) with 100 medical terms each.

### 6. Translation (Claude Sonnet 4.6)

The extracted data + drug info + glossary context are sent to Claude for simplification and translation.

**File:** `backend/app/services/translation.py` -> `simplify_and_translate()`

```
Build system prompt:
  -> Persona: caring health educator
  -> Rules: explain (not just translate), preserve drug names in English,
     never add clinical advice, flag low-confidence items, max 300 words
  -> Inject glossary context block

Build user prompt:
  -> Serialize PrescriptionData + DrugInfo list
  -> Specify target language
  -> Label low-confidence fields

Call Anthropic Claude Sonnet 4.6 Messages API
  -> Parse response into TranslationResult:
     - translated_text (full explanation)
     - per_medicine_summaries (one per medicine)
     - disclaimer
```

### 7. Text-to-Speech (Bhashini / Edge TTS -> S3)

The translated text is converted to spoken audio.

**File:** `backend/app/services/tts.py` -> `generate_and_deliver_audio()`

```
Format audio-friendly text:
  -> Strip emoji, markdown, bullets (webhooks.py -> _format_audio_text())
  -> Convert to flowing spoken sentences
  -> Cap at 2000 characters

TTS Provider Selection (automatic):
  -> If BHASHINI_API_KEY is set and non-empty: try Bhashini first
  -> If Bhashini fails or key is empty: fallback to Edge TTS (free, no API key)
  -> If both fail: return None (text-only delivery)

Upload to S3:
  -> Key: audio/{uuid4}.ogg (Bhashini) or audio/{uuid4}.mp3 (Edge TTS)
  -> Generate presigned URL (1 hour expiry)
  -> S3 lifecycle rule auto-deletes after 24 hours
```

**Edge TTS** (`backend/app/services/tts_edge.py`) supports 10 Indian languages with Microsoft Neural voices: Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, and Urdu. No API key required — just needs outbound internet access.

**Graceful degradation:** If both TTS providers and S3 fail, the pipeline continues with text-only delivery. Audio failure never blocks the text response.

### 8. Deliver Response (WhatsApp via Twilio)

**File:** `backend/app/api/webhooks.py` -> `_run_pipeline()` (steps 7-8)

```
Format text reply:
  -> Greeting + per-medicine cards (name, dosage, frequency, duration)
  -> Low-confidence warnings (marked with warning symbol)
  -> Disclaimer
  -> Enforce 1600 char WhatsApp limit (multi-level truncation)

Send via Twilio:
  -> Text message with formatted prescription summary
  -> Audio message (if TTS succeeded) with presigned S3 URL
  -> Fallback: text-only with "audio not available" note

Log interaction:
  -> Hash phone number (SHA-256, never store raw)
  -> Write metadata to PostgreSQL: timestamp, language, latency, status
  -> Clean up Redis session
```

### Error Handling

Pipeline errors are mapped to patient-friendly WhatsApp messages — no stack traces or technical details are ever exposed:

| Error | Patient Message |
|-------|----------------|
| Not a medical document | "This doesn't appear to be a medical document..." |
| Image not readable | "We couldn't read your image clearly..." |
| Translation failure | "We had trouble translating your prescription..." |
| Generic error | "Something went wrong, please try again..." |

### Web Upload Flow

In addition to WhatsApp, users can upload prescriptions directly via the web interface.

**Landing page:** `GET /` — served from `backend/templates/index.html`

**API endpoint:** `POST /api/translate` — `backend/app/api/web.py`

```
User opens http://<server>:8000/ in browser
  -> Selects language from dropdown (22 languages)
  -> Uploads prescription image (drag-and-drop or file picker)
  -> Frontend sends multipart POST to /api/translate

Server runs the same pipeline as WhatsApp:
  -> Validate image (type, size < 10MB) + language_code
  -> Extract prescription (GPT-4O Vision — from bytes, no URL download)
  -> Drug enrichment (Redis -> CSV -> API)
  -> Glossary lookup (Redis RAG)
  -> Translate (Claude Sonnet 4.6)
  -> TTS (Bhashini / Edge TTS -> S3)
  -> Return JSON response:
     {
       request_id, language_code, language_name,
       medicines: [{name, dosage, frequency, duration, confidence, purpose, side_effects}],
       translated_text, per_medicine_summaries, disclaimer,
       audio_url, latency_ms
     }

Frontend renders:
  -> Medicine cards with confidence badges
  -> Translated text block
  -> Audio player (if TTS succeeded)
  -> Disclaimer
```

**No API keys needed for web access** — the web interface uses the same backend pipeline. Edge TTS provides free audio without any additional configuration.

---

## Getting Started

### Prerequisites

- **Python 3.11+** installed
- **[uv](https://docs.astral.sh/uv/)** package manager (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Docker + Docker Compose** (for Docker setup)
- **API keys** (for running the actual pipeline — not needed for tests):
  - OpenAI (GPT-4O Vision)
  - Anthropic (Claude Sonnet 4.6)
  - Twilio (WhatsApp Business API) — only needed for WhatsApp, not for web
  - Bhashini (TTS — optional, Edge TTS works as free fallback with no key)
  - AWS (S3 for audio storage)

### Option A: Local Setup (without Docker)

This runs the FastAPI server directly on your machine. You'll need PostgreSQL and Redis running separately (or use Docker for just those).

```bash
# 1. Clone the repository
git clone https://github.com/nishantgaurav23/SehatSamjho.git
cd SehatSamjho

# 2. Create a Python 3.11 virtual environment
make venv
source .venv/bin/activate

# 3. Install all dependencies (runtime + dev tools: pytest, ruff)
make install-dev

# 4. Configure environment variables
cp .env.example .env
# Open .env and fill in your API keys and database URLs
# For local dev with Docker postgres/redis, the defaults in .env.example work

# 5. Run database migrations (requires PostgreSQL running)
make local-migrate

# 6. Seed drug database + medical glossary into Redis (requires Redis running)
make local-seed

# 7. Start the dev server with hot reload
make local-dev
# Server starts at http://localhost:8000

# 8. Verify it's running
curl http://localhost:8000/health
# {"status": "ok"}
```

### Option B: Docker Setup (recommended)

This starts the full stack — FastAPI app + PostgreSQL + Redis — with one command.

```bash
# 1. Clone the repository
git clone https://github.com/nishantgaurav23/SehatSamjho.git
cd SehatSamjho

# 2. Configure environment variables
cp .env.example .env
# Open .env and fill in your API keys
# DATABASE_URL and REDIS_URL are auto-configured by docker-compose

# 3. Start the full local stack (builds Docker image, starts postgres + redis + app)
make dev
# App starts at http://localhost:8000
# PostgreSQL at localhost:5432
# Redis at localhost:6379

# 4. Run database migrations (in a separate terminal)
make migrate

# 5. Seed drug database + glossary into Redis
make seed

# 6. Verify
curl http://localhost:8000/health
# {"status": "ok"}
```

### Connecting Twilio (for WhatsApp messaging)

After the server is running and accessible (locally via ngrok, or on EC2):

1. Go to the [Twilio Console](https://console.twilio.com/) -> Messaging -> Try it out -> Send a WhatsApp message
2. Set the webhook URL to: `http://<your-server>/webhook/whatsapp`
3. Method: POST
4. Send a test message from your phone to the Twilio WhatsApp sandbox number
5. You should receive the welcome message + language selection menu

---

## Environment Variables

Create a `.env` file at the project root (copy from `.env.example`):

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4O Vision extraction | `sk-...` |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude translation | `sk-ant-...` |
| `TWILIO_ACCOUNT_SID` | Twilio account SID | `ACxxxx...` |
| `TWILIO_AUTH_TOKEN` | Twilio auth token | `your-token` |
| `TWILIO_WHATSAPP_FROM` | Twilio WhatsApp sender number | `whatsapp:+14155238886` |
| `BHASHINI_API_KEY` | Bhashini TTS API key (optional — leave empty to use Edge TTS) | `your-key` or empty |
| `BHASHINI_USER_ID` | Bhashini user ID (optional — leave empty with API key) | `your-id` or empty |
| `AWS_ACCESS_KEY_ID` | AWS access key for S3 (optional — EC2 uses IAM role) | `AKIA...` or empty |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for S3 (optional — EC2 uses IAM role) | `your-secret` or empty |
| `S3_BUCKET` | S3 bucket name for audio files | `sehatsamjho-audio` |
| `DATABASE_URL` | PostgreSQL async connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/sehatsamjho` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |

**Note:** For production with Upstash Redis, use `rediss://` (with double-s for TLS).

---

## Running Tests

All external services (OpenAI, Anthropic, Bhashini, Edge TTS, Twilio, Redis, PostgreSQL, S3) are fully mocked — **no API keys or running services needed to run tests**.

```bash
# Run all 1468+ tests
make local-test

# Run a specific test file
source .venv/bin/activate
cd backend && python -m pytest tests/services/test_extraction_errors.py -v --tb=short

# Run tests by keyword
cd backend && python -m pytest tests/ -k "glossary" -v --tb=short

# Run tests inside Docker
make test
```

### Test Coverage by Area

| Test Area | Files | Tests |
|-----------|-------|-------|
| API / Webhooks / Pipeline | 13 | 260 |
| Services (extraction, translation, TTS, Edge TTS, drugs, glossary, WhatsApp) | 28 | 666 |
| Data Layer (DB, Redis, models, schemas) | 5 | 95 |
| Data Files (CSV, JSON validation) | 4 | 173 |
| Infrastructure (Dockerfile, Compose, migrations) | 7 | 112 |
| E2E smoke tests | 1 | 20 |
| **Total** | **58+** | **1468+** |

---

## Linting

```bash
make local-lint
```

Uses [Ruff](https://docs.astral.sh/ruff/) with 100-character line length. Checks formatting and lint rules in one pass.

---

## Deployment to AWS

The project is designed for AWS free-tier deployment. Infrastructure provisioning scripts are in `scripts/`.

### AWS Resources Needed

| Resource | Script | Tier |
|----------|--------|------|
| EC2 t3.micro (Ubuntu 22.04, ap-south-1) | `scripts/ec2-setup.sh` | Free tier |
| RDS db.t3.micro PostgreSQL | `scripts/rds-setup.sh` | Free tier |
| S3 bucket (audio storage, 24hr lifecycle) | `scripts/setup-s3.sh` | Free tier |
| IAM role (EC2 -> S3 access) | `scripts/setup-iam.sh` | Free |
| Upstash Redis (256MB, 10K req/day) | Manual (upstash.com) | Free tier |
| Elastic IP | Attached to EC2 | Free when attached |

### Deployment Steps

```bash
# 1. Provision AWS resources (run scripts or use AWS Console)
#    - Create EC2 instance with Docker installed
#    - Create RDS PostgreSQL database
#    - Create S3 bucket with 24hr lifecycle rule
#    - Create IAM role and attach to EC2
#    - Create Upstash Redis database

# 2. SSH into EC2
ssh -i your-key.pem ubuntu@<EC2_IP>

# 3. Clone the repository
git clone https://github.com/nishantgaurav23/SehatSamjho.git
cd SehatSamjho

# 4. Create production .env with all secrets
cp .env.example .env
# Edit .env with production values:
#   DATABASE_URL=postgresql+asyncpg://ssadmin:<password>@<RDS_ENDPOINT>:5432/sehatsamjho
#   REDIS_URL=rediss://default:<password>@<UPSTASH_ENDPOINT>:<PORT>
#   S3_BUCKET=sehatsamjho-audio-<account_id>
#   + all API keys

# 5. Deploy (builds prod Docker image, runs migrations + seed)
bash scripts/deploy.sh

# 6. Verify
curl http://localhost:8000/health
# {"status": "ok"}

# 7. Access the web interface
#    Open in browser: http://<EC2_ELASTIC_IP>:8000/

# 8. Configure Twilio webhook URL in Twilio Console (for WhatsApp)
#    URL: http://<EC2_ELASTIC_IP>:8000/webhook/whatsapp
#    Method: POST
```

### Redeployment

After pushing code changes:

```bash
ssh -i your-key.pem ubuntu@<EC2_IP>
cd SehatSamjho
bash scripts/deploy.sh
```

The deploy script pulls latest code, rebuilds the Docker image, runs migrations, and re-seeds data.

---

## Developer Commands

All commands are defined in the `Makefile`:

```bash
# ── Local Development ──
make venv           # Create .venv (Python 3.11)
make install        # Install runtime dependencies via uv
make install-dev    # Install runtime + dev dependencies (pytest, ruff)
make local-dev      # Start uvicorn with hot reload (port 8000)
make local-test     # Run pytest
make local-lint     # Run ruff check + format
make local-migrate  # Run alembic upgrade head
make local-seed     # Seed drugs + glossary into Redis

# ── Docker ──
make dev            # docker compose up --build (app + postgres + redis)
make test           # Run pytest in Docker container
make migrate        # Run alembic in Docker container
make seed           # Seed data in Docker container
```

---

## Privacy and Security

| Principle | Implementation |
|-----------|---------------|
| **Zero PHI storage** | No raw images, prescriptions, or patient data persisted anywhere |
| **Phone hashing** | Phone numbers SHA-256 hashed before any logging |
| **Metadata-only logs** | Only: timestamp, language, doc_type, latency, status, error_code |
| **HMAC verification** | Every webhook validated via Twilio HMAC signature |
| **Ephemeral audio** | S3 audio files auto-deleted after 24 hours |
| **No hardcoded secrets** | All API keys via `.env` -> pydantic-settings |
| **Transient sessions** | Redis sessions expire after 30 minutes |

---

## Development Progress

Built using **spec-driven development** (TDD). Each spec has a dedicated folder under `specs/` with a detailed specification (`spec.md`) and implementation checklist (`checklist.md`). The full spec index is in `roadmap.md`.

| Phase | Name | Specs | Status |
|-------|------|-------|--------|
| 1 | Project Setup | S1.1 -- S1.5 | Done |
| 2 | Data Layer | S2.1 -- S2.5 | Done |
| 3 | WhatsApp Channel | S3.1 -- S3.5 | Done |
| 4 | Webhook State Machine | S4.1 -- S4.6 | Done |
| 5 | GPT-4O Vision Extraction | S5.1 -- S5.5 | Done |
| 6 | Medical Glossary | S6.1 -- S6.4 | Done |
| 7 | Translation | S7.1 -- S7.5 | Done |
| 8 | Drug Lookup | S8.1 -- S8.5 | Done |
| 9 | TTS & Audio Delivery | S9.1 -- S9.5 | Done |
| 10 | Pipeline Integration | S10.1 -- S10.5 | Done |
| 11 | Infra & Seeding | S11.1 -- S11.7 | Done |
| 12 | AWS Deployment | S12.1 -- S12.7 | Done |
| 13 | QA & Handover | S13.1 -- S13.5 | In Progress |
| 14 | Web Interface | S14.1 -- S14.4 | Done (S14.1-S14.3), S14.4 pending |

**67 / 73 specs complete** — core application, deployment, and web interface complete.

---

## Cost Estimate (Prototype)

| Resource | Monthly Cost |
|----------|-------------|
| EC2 t3.micro | $0 (free tier) |
| RDS db.t3.micro PostgreSQL | $0 (free tier) |
| S3 audio storage | $0 (free tier) |
| Upstash Redis | $0 (free tier) |
| Edge TTS (Microsoft Neural) | $0 (free, no API key) |
| OpenAI GPT-4O Vision | ~$5 / 1000 documents |
| Claude Sonnet 4.6 | ~$2 / 1000 documents |
| Twilio WhatsApp | ~$1-5 during testing |
| **Total** | **~$8-15/month** |

---

## License

MIT
