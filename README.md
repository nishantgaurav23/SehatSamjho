# SehatSamjho — AI Medical Document Translator

> A WhatsApp bot that photographs Indian prescriptions and lab reports,
> translates them into the patient's language, and reads them aloud.
> Built for the 9 out of 10 Indian adults who have low health literacy.

---

## Problem

Medical documents in India are written in English medical jargon.
Most patients speak only their regional language and many cannot read.
SehatSamjho fills this gap — it takes any medical document, extracts the content,
translates it into the patient's language at an 8th-grade reading level, and reads it aloud.
All via WhatsApp. No app install required.

---

## How It Works (End-to-End Flow)

```
1. Patient sends prescription photo on WhatsApp
         ↓
2. Twilio receives the image → POSTs to /webhook/whatsapp
         ↓
3. webhooks.py checks Redis for user session state
   (which language did they pick? what step are they on?)
         ↓
4. extraction.py → GPT-4o Vision API
   → structured JSON: medicines, dosages, confidence scores
         ↓
5. drug_lookup.py → Redis cache → local CSV → IndianMedicineDB API
   → enriches each medicine with: uses, side effects, timing
         ↓
6. translation.py → GPT-4o with medical glossary injected
   → plain-language explanation in patient's chosen language
         ↓
7. tts.py → Bhashini TTS API → audio → compressed to <500KB → S3
         ↓
8. whatsapp.py → Twilio REST API
   → sends text card + voice message back to patient
         ↓
9. db/models.py → logs metadata to PostgreSQL
   (timestamp, language, doc_type, latency — NO patient content stored)
```

---

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Patient    │────▶│   Twilio     │────▶│  FastAPI Backend │
│  (WhatsApp)  │◀────│  WhatsApp    │◀────│  (webhooks.py)   │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                              ┌────────────────────┼───────────────────┐
                              ▼                    ▼                   ▼
                       ┌──────────┐         ┌──────────┐       ┌──────────────┐
                       │ GPT-4o   │         │ Drug DB  │       │ Bhashini TTS │
                       │ Vision + │         │ (Redis + │       │ (22 langs)   │
                       │   LLM    │         │   CSV)   │       └──────────────┘
                       └──────────┘         └──────────┘
                                                   │
                              ┌────────────────────┼───────────────────┐
                              ▼                    ▼                   ▼
                       ┌──────────┐         ┌──────────┐       ┌──────────────┐
                       │PostgreSQL│         │  Redis   │       │  S3 (audio)  │
                       │(metadata)│         │(sessions)│       │   storage    │
                       └──────────┘         └──────────┘       └──────────────┘
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Messaging | WhatsApp via Twilio | 400M+ Indian users, works on 2G, no app install |
| Backend | Python / FastAPI | Async, fast, strong ML ecosystem |
| OCR + Extraction | GPT-4o Vision | 98.6% accuracy on medical Hindi (AIIMS study) |
| Simplification | GPT-4o LLM | Same model, chained call, avoids multi-model complexity |
| Translation Fallback | IndicTrans2 (AI4Bharat) | Open-source, 22 languages, self-hostable |
| Drug Database | IndianMedicineDB API + Redis | 400K+ Indian medicines, cached for <100ms lookups |
| Text-to-Speech | Bhashini TTS | Free, government-backed, 22 scheduled Indian languages |
| Database | PostgreSQL (via SQLAlchemy) | Metadata and analytics only — zero PHI |
| Session State | Redis | User conversation state between webhook calls |
| Audio Storage | AWS S3 | Presigned URLs for Twilio audio delivery |
| Hosting | AWS ECS (ap-south-1 Mumbai) | Data residency in India, DPDP compliance |
| CI/CD | GitHub Actions | Auto-deploy on merge to main |

---

## Project Structure

```
SehatSamjho/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app entry point
│   │   ├── api/
│   │   │   ├── webhooks.py       # WhatsApp webhook handler + state machine
│   │   │   └── dashboard.py      # B2B dashboard API endpoints
│   │   ├── core/
│   │   │   └── config.py         # All settings loaded from .env
│   │   ├── services/
│   │   │   ├── extraction.py     # GPT-4o Vision — extract medicines from image
│   │   │   ├── translation.py    # GPT-4o — simplify + translate to patient language
│   │   │   ├── tts.py            # Bhashini TTS — text to audio
│   │   │   ├── drug_lookup.py    # Drug DB — Redis + CSV + API lookup
│   │   │   └── whatsapp.py       # Twilio client — send messages
│   │   ├── db/
│   │   │   ├── database.py       # SQLAlchemy async engine + session factory
│   │   │   └── models.py         # PostgreSQL table definitions (metadata only)
│   │   └── models/
│   │       └── schemas.py        # Pydantic request/response models
│   ├── Dockerfile
│   ├── requirements.txt
│   └── alembic/                  # Database migrations
│       └── versions/
├── data/
│   ├── drugs/
│   │   └── top_medicines.csv     # 500+ common Indian medicines (offline cache)
│   └── glossary/
│       └── hindi_terms.json      # Curated medical term translations
├── scripts/
│   ├── fetch_drug_data.py        # Downloads + builds the drug database
│   ├── seed_drug_db.py           # Loads drug CSV into Redis
│   └── seed_glossary.py          # Loads glossary JSON into Redis
├── infra/
│   ├── ecs-task-definition.json  # AWS ECS container config
│   └── README.md                 # AWS setup steps
├── .github/
│   └── workflows/
│       ├── ci.yml                # Lint + test on every PR
│       └── deploy.yml            # Build + push to ECR + deploy to ECS on merge
├── .env.example                  # Template for all environment variables
├── docker-compose.yml            # Local dev: api + postgres + redis
├── docker-compose.prod.yml       # Production overrides (external DB/Redis)
├── Makefile                      # All developer commands
└── CHECKLIST.md                  # Day-by-day prototype checklist
```

---

## File-by-File Explanation

### Root Configuration Files

#### `.env.example`
Every API key, database URL, feature flag, and secret the app needs.
Developers copy this to `.env` and fill it in. The `.env` file is git-ignored
so secrets never get committed. The backend validates all required values at
startup — if something is missing, it refuses to start with a clear error.

#### `Makefile`
Wraps all common developer commands so nobody has to memorize Docker/alembic/pytest flags.
`make dev`, `make migrate`, `make seed`, `make test`, `make ngrok`, `make build-push`.

#### `docker-compose.yml`
Starts 3 services locally: the API, PostgreSQL, and Redis. Docker handles networking
between them. The API mounts your local `backend/` folder so code edits hot-reload.

#### `docker-compose.prod.yml`
Production overrides. Strips out local Postgres/Redis containers (replaced by AWS RDS
and ElastiCache). Used by GitHub Actions deploy pipeline.

#### `.gitignore`
Ensures `.env`, `__pycache__`, audio temp files, and large datasets are never committed.

---

### Backend: `backend/app/core/config.py`
Single place where all environment variables are loaded and validated using Pydantic.
Every service imports `settings` from here. Prevents `os.getenv()` scattered everywhere.
If a required key is missing at startup, app fails immediately with a clear error message.

### Backend: `backend/app/main.py`
FastAPI application entry point. On startup: creates DB tables, connects to Redis.
Registers two route groups: `/webhook` (Twilio) and `/api/dashboard` (B2B partners).
Provides `/health` endpoint — AWS ECS pings this every 30s to check the container is alive.

### Backend: `backend/app/api/webhooks.py`
The most important file. Twilio calls this on every patient WhatsApp message.
Implements a state machine (stored in Redis per user):
- `IDLE` → greeting → send language selection buttons
- `AWAITING_LANGUAGE` → patient taps language → store in Redis → ask for photo
- `AWAITING_DOCUMENT` → patient sends image → send "please wait..." → start pipeline
- `PROCESSING` → extract → translate → TTS → send response → reset to IDLE

### Backend: `backend/app/services/extraction.py`
Calls GPT-4o Vision with the prescription image URL. Returns structured JSON
with medicines, dosages, confidence scores. Low-confidence fields (illegible handwriting)
are flagged — these show up with ⚠️ in the patient's response.

### Backend: `backend/app/services/translation.py`
Takes extracted JSON + target language. Injects medical glossary as context.
Calls GPT-4o to simplify jargon and translate. Preserves drug names and dosage
numbers in English alongside the translation. Appends safety disclaimer.

### Backend: `backend/app/services/tts.py`
Calls Bhashini TTS API with translated text + language code. Gets back base64 audio.
Decodes → compresses to <500KB with pydub → uploads to S3 → returns presigned URL.
Fallback: if Bhashini is unavailable, returns None and webhook sends text-only response.

### Backend: `backend/app/services/drug_lookup.py`
For each medicine name extracted, looks up: generic name, uses, side effects, timing.
Lookup chain: Redis cache (fastest) → local CSV → IndianMedicineDB API (slowest).
Warm cache hit rate target: >70% after first few hundred requests.

### Backend: `backend/app/services/whatsapp.py`
Twilio client wrapper. Parses incoming webhook form data. Sends text messages,
voice messages, and quick-reply language buttons back to the patient.

### Backend: `backend/app/db/models.py`
PostgreSQL schema. Stores ONLY metadata per translation — timestamp, language,
doc_type, confidence_avg, latency_ms, success. Zero patient content. Powers B2B dashboard.

### Backend: `backend/app/models/schemas.py`
Pydantic models defining data shapes flowing between services.
Used by FastAPI for request/response validation and by services to pass
structured data to each other (extraction result → translation → TTS).

---

### Data & Scripts

#### `data/drugs/top_medicines.csv`
500+ most commonly prescribed Indian medicines with: brand name, generic name,
drug class, uses, side effects, food interactions. Loaded into Redis on startup.
Built by running `scripts/fetch_drug_data.py`.

#### `data/glossary/hindi_terms.json`
Curated medical term translations — diagnoses, lab tests, prescription abbreviations
(OD, BD, TDS, HS, AC, PC) — in Hindi and other languages. Reviewed by bilingual
medical professionals. Injected into GPT-4o translation prompt to ensure consistency.
This glossary is the long-term data moat: better glossary = more accurate translations.

#### `scripts/fetch_drug_data.py`
Downloads drug data from OpenFDA, WHO Essential Medicines List, and a seed list
of common Indian medicines. Outputs `data/drugs/top_medicines.csv`.

#### `scripts/seed_drug_db.py` / `scripts/seed_glossary.py`
Load CSV and JSON data into Redis so the API can use them. Run via `make seed`.

---

### CI/CD & Infrastructure

#### `.github/workflows/ci.yml`
Runs on every PR: lint (ruff) + tests (pytest) + docker build.
PRs to `main` require this to pass.

#### `.github/workflows/deploy.yml`
Runs on merge to `main`: build Docker image → push to AWS ECR →
update ECS service → zero-downtime rolling deploy.

#### `infra/ecs-task-definition.json`
Tells AWS ECS how to run the container: CPU, memory, env vars (from SSM Parameter Store),
IAM role, CloudWatch log group. Registered by the deploy workflow.

---

## Developer Branches

| Developer | Branch |
|-----------|--------|
| Nishant | `feature/sehatsamjo-nishant` |
| Dev 2 | `feature/sehatsamjo-dev2` |

Both branches merge to `main` via PR with CI required.

---

## Local Setup (First Time)

```bash
# 1. Clone and switch to your branch
git clone https://github.com/nishantgaurav23/SehatSamjho.git
cd SehatSamjho
git checkout feature/sehatsamjo-nishant

# 2. Copy env template and fill in your API keys
cp .env.example .env
# Edit .env with your OpenAI, Twilio, Bhashini keys

# 3. First-time setup (pulls Docker images, runs migrations, seeds data)
make setup

# 4. Start the dev server (hot-reload)
make dev
# API running at http://localhost:8000
# Docs at http://localhost:8000/docs

# 5. In a separate terminal — open Twilio webhook tunnel
make ngrok
# Copy the https URL → set it in Twilio console as webhook URL
```

---

## API Keys You Need

| Service | Where to Get | Required for |
|---------|-------------|-------------|
| OpenAI | platform.openai.com | GPT-4o extraction + translation |
| Twilio | console.twilio.com | WhatsApp send/receive |
| Bhashini | bhashini.gov.in (free) | Text-to-speech audio |
| AWS | AWS Console | S3 audio + deployment |
| PostHog | posthog.com (free tier) | Analytics |

---

## Privacy & Compliance

- Patient images are processed in-memory — never written to disk or database
- PostgreSQL stores only metadata: timestamp, language, doc_type, latency. Zero PHI
- Informed consent message sent to every new user on first interaction
- Every response includes disclaimer: "This is a simplified translation. Always follow your doctor's advice."
- All infrastructure in AWS Mumbai (ap-south-1) for DPDP Act 2023 data residency
- TLS 1.3 in transit, AES-256 at rest

---

## Useful Commands

```bash
make dev          # Start local dev server (hot reload)
make up           # Start services in background
make down         # Stop all services
make logs         # Follow API logs
make migrate      # Run database migrations
make seed         # Load drug database + glossary into Redis
make test         # Run test suite
make lint         # Lint + format check
make ngrok        # Start ngrok tunnel for Twilio
make build-push   # Build + push Docker image to AWS ECR
make deploy-staging  # Deploy to AWS staging
```

---

## Target: 3-Day Working Prototype

| Day | Focus | Exit Criteria |
|-----|-------|--------------|
| Feb 26 | Setup + GPT-4o Vision + WhatsApp webhook | Bot receives image, responds with text |
| Feb 27 | Translation + Bhashini TTS + Drug lookup | Full flow: photo → Hindi text + voice |
| Feb 28 | Testing + Data + Polish | 5 languages working, Docker-ready, demo-able |

See `CHECKLIST.md` for the full day-by-day task list.
