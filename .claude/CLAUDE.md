# SehatSamjho — Claude Code Context

## Project
AI Medical Document Translator via WhatsApp.
Patients photograph prescriptions → receive plain-language translation + audio in their language.
Backend: Python / FastAPI. Deployment: AWS ECS (ap-south-1).

## Developers
- Nishant (nishantgaurav23@gmail.com) → branch: feature/sehatsamjo-nishant
- Dev 2 → branch: feature/sehatsamjo-dev2
- Main branch: production-standard empty structure. All code via feature branches → PR → main.

## Key Rules
- NEVER commit to main directly. Always use feature branches.
- NEVER store patient data (PHI). Only metadata logs (timestamp, language, doc_type, latency).
- NEVER hardcode API keys. All secrets via .env → config.py.
- NEVER add Claude as co-author in commits.
- Git author: nishantgaurav23 / nishantgaurav23@gmail.com

## Tech Stack
- FastAPI + uvicorn (async, --workers 4 in prod)
- PostgreSQL via SQLAlchemy async + asyncpg
- Redis (sessions + drug cache)
- OpenAI GPT-4o (Vision extraction + LLM translation)
- Bhashini TTS (22 Indian languages, free)
- Twilio (WhatsApp send/receive)
- AWS S3 (audio storage), ECS (hosting), ECR (container registry)

## Project Structure
```
backend/app/
├── main.py              # FastAPI entry point
├── api/
│   ├── webhooks.py      # Twilio WhatsApp webhook + state machine
│   └── dashboard.py     # B2B analytics endpoints
├── core/
│   ├── config.py        # All settings from .env (pydantic-settings)
│   └── security.py      # Auth + Twilio HMAC verification
├── db/
│   ├── database.py      # Async SQLAlchemy engine + get_db()
│   └── models.py        # PostgreSQL table definitions (metadata only)
├── models/
│   └── schemas.py       # Pydantic request/response models
└── services/
    ├── extraction.py    # GPT-4o Vision → structured JSON
    ├── translation.py   # GPT-4o simplify + translate + glossary RAG
    ├── tts.py           # Bhashini TTS → audio → S3
    ├── drug_lookup.py   # Redis → CSV → IndianMedicineDB API
    └── whatsapp.py      # Twilio client (send text, audio, buttons)
```

## Core Flow
```
Patient WhatsApp → Twilio POST /webhook/whatsapp
→ webhooks.py (Redis session state machine)
→ extraction.py (GPT-4o Vision)
→ drug_lookup.py (Redis/CSV/API)
→ translation.py (GPT-4o + medical glossary RAG)
→ tts.py (Bhashini → S3)
→ whatsapp.py (Twilio send text + audio)
→ db/models.py (log metadata, zero PHI)
```

## Commands
```bash
make dev          # Start local server (hot reload)
make migrate      # Run DB migrations
make seed         # Load drug DB + glossary into Redis
make test         # Run tests
make ngrok        # Tunnel for Twilio webhook
make build-push   # Build + push to AWS ECR
```

## Code Standards
- Async everywhere (async def, await, AsyncSession)
- Every file has a module docstring explaining what it does and how it integrates
- Inline comments on non-obvious logic
- Pydantic models for all data in/out
- Tenacity for retry logic on all external API calls (OpenAI, Bhashini, Twilio)
- Loguru for logging — always include request_id in log context
- Ruff for linting and formatting (line length: 100)

## Prototype Timeline
- Day 1 (Feb 26): Webhook + GPT-4o extraction working
- Day 2 (Feb 27): Translation + Bhashini TTS + drug lookup
- Day 3 (Feb 28): Testing + data + Docker working end-to-end
- Day 6 (Mar 3): AWS deployment
- Day 7 (Mar 4): Handover
