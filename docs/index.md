# SehatSamjho — Documentation Index

All file-by-file explanations, architecture notes, setup guides, and deployment
instructions live here. Read in order if you're new to the project.

---

## Table of Contents

### 1. Project Understanding
- [Architecture & Flow](./01-architecture.md) — How the system works end to end
- [Tech Stack Decisions](./01-architecture.md#tech-stack) — Why each tool was chosen

### 2. Infrastructure Guide (Start Here)
- [**Infrastructure Guide**](./03-infrastructure-guide.md) — File integration map, how to run, send data, verify results, common errors

### 3. Configuration Files
- [`.env.example`](./config/02-env-example.md) — All environment variables explained
- [`Makefile`](./config/03-makefile.md) — Every developer command explained
- [`docker-compose.yml`](./config/04-docker-compose.md) — Local services setup
- [`docker-compose.prod.yml`](./config/05-docker-compose-prod.md) — Production overrides
- [`.gitignore`](./config/06-gitignore.md) — What gets excluded and why

### 3. Backend — Entry Point
- [`backend/requirements.txt`](./backend/07-requirements.md) — Every Python package and why
- [`backend/Dockerfile`](./backend/08-dockerfile.md) — How the container is built
- [`backend/app/main.py`](./backend/09-main.md) — FastAPI app entry point
- [`backend/app/core/config.py`](./backend/10-config.md) — Settings and env loading

### 4. Backend — API Layer
- [`backend/app/api/webhooks.py`](./backend/11-webhooks.md) — WhatsApp state machine (core)
- [`backend/app/api/dashboard.py`](./backend/12-dashboard.md) — B2B dashboard endpoints

### 5. Backend — Services (Core Logic)
- [`backend/app/services/whatsapp.py`](./backend/13-whatsapp-service.md) — Twilio client
- [`backend/app/services/extraction.py`](./backend/14-extraction.md) — GPT-4o Vision
- [`backend/app/services/translation.py`](./backend/15-translation.md) — GPT-4o Simplify + Translate
- [`backend/app/services/tts.py`](./backend/16-tts.md) — Bhashini Text-to-Speech
- [`backend/app/services/drug_lookup.py`](./backend/17-drug-lookup.md) — Drug database lookup

### 6. Backend — Database Layer
- [`backend/app/db/database.py`](./backend/18-database.md) — PostgreSQL connection
- [`backend/app/db/models.py`](./backend/19-db-models.md) — Table definitions
- [`backend/app/models/schemas.py`](./backend/20-schemas.md) — Pydantic data models

### 7. Data & Scripts
- [`data/drugs/top_medicines.csv`](./data/21-drug-data.md) — Drug database explained
- [`data/glossary/hindi_terms.json`](./data/22-glossary.md) — Medical glossary explained
- [`scripts/fetch_drug_data.py`](./data/23-fetch-drugs.md) — How drug data is gathered
- [`scripts/seed_drug_db.py`](./data/24-seed.md) — Loading data into Redis

### 8. CI/CD & Infrastructure
- [`.github/workflows/ci.yml`](./infra/25-ci.md) — Lint + test on every PR
- [`.github/workflows/deploy.yml`](./infra/26-deploy.md) — Auto-deploy to AWS
- [`infra/ecs-task-definition.json`](./infra/27-ecs.md) — AWS ECS container config
- [AWS Setup Guide](./infra/28-aws-setup.md) — Step-by-step AWS infrastructure

### 9. Planning
- [Prototype Checklist](../CHECKLIST.md) — Day-by-day tasks (Feb 26 – Mar 4)
- [Data Gathering Plan](./data/21-drug-data.md) — Where drug + glossary data comes from

---

## Quick Reference

```bash
make setup        # First-time setup
make dev          # Start dev server
make ngrok        # Open Twilio webhook tunnel
make migrate      # Run DB migrations
make seed         # Load drug + glossary data
make test         # Run tests
make build-push   # Deploy to AWS
```

## Two-Developer Branch Strategy

| Developer | Branch | Focus |
|-----------|--------|-------|
| Nishant | `feature/sehatsamjo-nishant` | Webhook, Twilio, TTS, Docker, AWS |
| Dev 2 | `feature/sehatsamjo-dev2` | GPT-4o, Translation, Drug DB, Data |

Both branches merge to `main` via PR. CI must pass before merge.
