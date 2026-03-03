# SehatSamjho — AI Medical Document Translator

Patients photograph prescriptions on WhatsApp and receive plain-language translations with audio in their chosen Indian language.

## How It Works

```
Patient sends prescription photo via WhatsApp
  → GPT-4O Vision extracts medicines, dosages, instructions
  → Drug database enriches with purpose, side effects, interactions
  → Medical glossary grounds terminology in patient's language
  → Claude Sonnet 4.6 simplifies and translates to chosen language
  → Bhashini TTS generates audio summary
  → Patient receives text + audio reply on WhatsApp
```

## Architecture

### Processing Pipeline

```mermaid
flowchart LR
    A["📱<br/><b>Photo Sent</b><br/>WhatsApp"]:::s1
    B["📲<br/><b>Received</b><br/>Twilio"]:::s2
    C["👁️<br/><b>Extracted</b><br/>GPT-4O"]:::s3
    D["💊<br/><b>Enriched</b><br/>Drug DB"]:::s4
    E["📖<br/><b>Grounded</b><br/>Glossary"]:::s5
    F["🤖<br/><b>Translated</b><br/>Claude"]:::s6
    G["🔊<br/><b>Spoken</b><br/>Bhashini"]:::s7
    H["📱<br/><b>Delivered</b><br/>Text + Audio"]:::s8

    A --> B --> C --> D --> E --> F --> G --> H

    classDef s1 fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
    classDef s2 fill:#9C27B0,stroke:#7B1FA2,stroke-width:2px,color:#fff
    classDef s3 fill:#FF9800,stroke:#E65100,stroke-width:2px,color:#fff
    classDef s4 fill:#00BCD4,stroke:#00838F,stroke-width:2px,color:#fff
    classDef s5 fill:#009688,stroke:#00695C,stroke-width:2px,color:#fff
    classDef s6 fill:#3F51B5,stroke:#283593,stroke-width:2px,color:#fff
    classDef s7 fill:#E91E63,stroke:#AD1457,stroke-width:2px,color:#fff
    classDef s8 fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
```

### System Overview

```mermaid
flowchart TB
    P["📱 Patient · WhatsApp"]:::green

    subgraph GW["📲 Messaging Gateway"]
        TW["Twilio WhatsApp Business API"]
    end

    subgraph BE["⚡ FastAPI Backend · Python 3.11 Async"]
        WH["🔗 Webhook Endpoint"]:::blue
        SEC["🔒 HMAC Verification"]:::blue
        SM["🔄 Session State Machine"]:::blue
        EXT["👁️ GPT-4O Vision · Extraction"]:::orange
        DRUG["💊 Drug Lookup · Redis/CSV"]:::cyan
        GLOSS["📖 Medical Glossary · RAG"]:::teal
        TRANS["🤖 Claude Sonnet 4.6 · Translation"]:::indigo
        TTS["🔊 Bhashini TTS · 22 Languages"]:::pink
        SEND["📨 WhatsApp Reply Sender"]:::blue
    end

    subgraph DS["💾 Data Stores"]
        PG[("🐘 PostgreSQL<br/><i>Metadata · Zero PHI</i>")]:::grey
        REDIS[("⚡ Redis<br/><i>Sessions · Cache</i>")]:::grey
        S3[("☁️ AWS S3<br/><i>Audio · 24hr TTL</i>")]:::grey
    end

    P <-->|"Messages"| TW
    TW -->|"POST /webhook"| WH
    WH --> SEC --> SM
    SM --> EXT --> DRUG --> GLOSS --> TRANS --> TTS --> SEND
    SEND -->|"Text + Audio"| TW

    SM <-.->|"Sessions"| REDIS
    DRUG <-.->|"Drug Cache"| REDIS
    GLOSS <-.->|"Term Cache"| REDIS
    SM -.->|"Log"| PG
    TTS -.->|"Upload"| S3

    style GW fill:#F3E5F5,stroke:#9C27B0,stroke-width:2px,color:#4A148C
    style BE fill:#E3F2FD,stroke:#1976D2,stroke-width:2px,color:#0D47A1
    style DS fill:#ECEFF1,stroke:#607D8B,stroke-width:2px,color:#37474F

    classDef green fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
    classDef purple fill:#9C27B0,stroke:#7B1FA2,stroke-width:2px,color:#fff
    classDef blue fill:#1976D2,stroke:#0D47A1,stroke-width:2px,color:#fff
    classDef orange fill:#FF9800,stroke:#E65100,stroke-width:2px,color:#fff
    classDef indigo fill:#3F51B5,stroke:#283593,stroke-width:2px,color:#fff
    classDef cyan fill:#00BCD4,stroke:#00838F,stroke-width:2px,color:#fff
    classDef teal fill:#009688,stroke:#00695C,stroke-width:2px,color:#fff
    classDef pink fill:#E91E63,stroke:#AD1457,stroke-width:2px,color:#fff
    classDef grey fill:#607D8B,stroke:#37474F,stroke-width:2px,color:#fff

    class TW purple
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Messaging | Twilio WhatsApp Business API |
| Backend | Python 3.11 / FastAPI / uvicorn (async) |
| Vision / Extraction | OpenAI GPT-4O Vision |
| Translation | Anthropic Claude Sonnet 4.6 |
| TTS | Bhashini (22 Indian languages) |
| Database | PostgreSQL (async SQLAlchemy + asyncpg) |
| Cache / Sessions | Redis |
| Audio Storage | AWS S3 (presigned URLs, 24hr lifecycle) |
| Hosting | AWS EC2 t3.micro (ap-south-1) |

## Supported Languages

Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Odia, Punjabi, Assamese, Urdu, Kashmiri, Sindhi, Konkani, Maithili, Dogri, Manipuri, Santali, Nepali, Bodo, Sanskrit

## Local Setup

```bash
# 1. Create virtual environment
make venv
source .venv/bin/activate

# 2. Install dependencies (dev extras include pytest, ruff)
make install-dev

# 3. Copy and fill environment variables
cp .env.example .env
# Edit .env with your API keys

# 4. Run the dev server
make local-dev
# Server starts at http://localhost:8000

# 5. Verify health
curl http://localhost:8000/health
# {"status": "ok"}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (GPT-4O Vision extraction) |
| `ANTHROPIC_API_KEY` | Anthropic API key (Claude translation) |
| `TWILIO_ACCOUNT_SID` | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_WHATSAPP_FROM` | Twilio WhatsApp sender (e.g. `whatsapp:+14155238886`) |
| `BHASHINI_API_KEY` | Bhashini TTS API key |
| `BHASHINI_USER_ID` | Bhashini user ID |
| `AWS_ACCESS_KEY_ID` | AWS access key for S3 |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key for S3 |
| `S3_BUCKET` | S3 bucket name for audio files |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |

## Running Tests

```bash
# All tests
make local-test

# Specific test file
cd backend && python -m pytest tests/services/test_send_audio_message.py -v --tb=short
```

All external services (OpenAI, Anthropic, Bhashini, Twilio, Redis, DB) are fully mocked in tests.

## Linting

```bash
make local-lint
```

Uses Ruff with 100-char line length.

## Docker

```bash
# Local dev stack (app + PostgreSQL + Redis)
make dev

# Run tests in container
make test

# Run migrations
make migrate

# Seed drug database + glossary into Redis
make seed
```

## Project Structure

```
backend/app/
├── main.py              # FastAPI app factory + /health
├── api/
│   ├── webhooks.py      # Twilio WhatsApp webhook + state machine
│   └── dashboard.py     # B2B analytics endpoints
├── core/
│   ├── config.py        # pydantic-settings (all env vars)
│   └── security.py      # Twilio HMAC signature verification
├── db/
│   ├── database.py      # Async SQLAlchemy engine + session
│   ├── redis.py         # Async Redis client
│   └── models.py        # InteractionLog table (metadata only, zero PHI)
├── models/
│   └── schemas.py       # Pydantic request/response models
└── services/
    ├── whatsapp.py      # Language data + Twilio messaging helpers
    ├── extraction.py    # GPT-4O Vision → PrescriptionData
    ├── translation.py   # Claude Sonnet 4.6 translation + glossary RAG
    ├── tts.py           # Bhashini TTS → S3 audio
    ├── drug_lookup.py   # Redis/CSV/API drug enrichment
    └── glossary.py      # Medical glossary loader + Redis lookup
```

## Privacy

- Zero PHI (Protected Health Information) stored
- Phone numbers hashed (SHA-256) before logging
- No raw images, prescriptions, or patient data persisted
- Only metadata logged: timestamp, language, doc_type, latency, status
