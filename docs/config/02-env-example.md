# File: `.env.example`

## What It Is
A template listing every environment variable the application needs to run.
It is the single source of truth for all configuration.

## Why It Exists
- Keeps all secrets (API keys, passwords, database URLs) out of the codebase
- `.env` is git-ignored. `.env.example` is committed so new developers
  know exactly what keys they need without having to read all the source code
- Acts as living documentation — when a new service is added, its key goes here first
- Pydantic (`config.py`) reads this at startup and refuses to start if a
  required key is missing — better to fail loudly at boot than silently during a request

## How It Connects to the Rest of the Project

```
.env.example  ──(developer copies)──▶  .env
                                          │
                                          ▼
                                    config.py  (pydantic-settings reads .env)
                                          │
                        ┌─────────────────┼──────────────────┐
                        ▼                 ▼                  ▼
                  extraction.py     whatsapp.py           tts.py
                  (OPENAI_API_KEY)  (TWILIO_*)        (BHASHINI_*)
                        │
                        ▼
                  Also used by GitHub Actions (secrets stored in repo settings)
                  Also used by AWS ECS (pulled from SSM Parameter Store in prod)
```

## Section-by-Section Breakdown

### `ENVIRONMENT`
Controls which mode the app runs in: `development`, `staging`, or `production`.
In `production`, Swagger docs (`/docs`) are disabled, CORS is locked to your domain,
and Twilio signature validation is enforced.

---

### OpenAI
```
OPENAI_API_KEY      — Your GPT-4o API key. Every patient request costs ~₹4.5 here.
OPENAI_MODEL        — Default: gpt-4o. Don't change unless testing cost optimisations.
OPENAI_MAX_TOKENS   — 2000 is enough for a full prescription summary under 300 words.
OPENAI_TIMEOUT_SECONDS — 45s. GPT-4o Vision can be slow on complex images. Don't set lower.
```
**Where to get:** platform.openai.com → API Keys

---

### Twilio
```
TWILIO_ACCOUNT_SID      — Found on Twilio console dashboard
TWILIO_AUTH_TOKEN       — Found on Twilio console dashboard (keep secret)
TWILIO_WHATSAPP_NUMBER  — Sandbox: whatsapp:+14155238886
                          Production: your approved WhatsApp Business number
```
**Where to get:** console.twilio.com
**Sandbox setup:** Join Twilio WhatsApp sandbox by sending "join <word>" to +14155238886

---

### Bhashini TTS
```
BHASHINI_API_KEY        — Register at bhashini.gov.in (free for startups)
BHASHINI_USER_ID        — Your user ID from the Bhashini dashboard
BHASHINI_PIPELINE_URL   — Leave as default. This is the Dhruva inference endpoint.
```
**Where to get:** bhashini.gov.in → Register → API Access
**Cost:** Free (government-backed)

---

### Database (PostgreSQL)
```
DATABASE_URL  — SQLAlchemy async connection string format:
                postgresql+asyncpg://user:password@host:port/dbname

Local dev:    postgresql+asyncpg://sehat:sehatpassword@postgres:5432/sehatsamjho
              (docker-compose sets host to "postgres" — the service name)

Staging/Prod: postgresql+asyncpg://sehat:<password>@<rds-endpoint>:5432/sehatsamjho
```
**Note:** Docker Compose injects this automatically in the `environment:` block,
so you don't need to set it in `.env` for local dev. But having it in `.env` is
useful when running the API outside Docker (e.g., directly with `uvicorn`).

---

### Redis
```
REDIS_URL  — Connection string for Redis.

Local dev:  redis://redis:6379/0     (service name "redis" from docker-compose)
Staging:    redis://<elasticache-endpoint>:6379/0
```
Redis is used for two things:
1. User session state (which language, which step of the conversation)
2. Drug lookup cache (so the same medicine isn't looked up twice)

---

### AWS
```
AWS_ACCESS_KEY_ID       — IAM user key (for local dev / CI)
AWS_SECRET_ACCESS_KEY   — IAM user secret
AWS_REGION              — ap-south-1 (Mumbai) — data residency requirement
AWS_S3_BUCKET           — Bucket name for storing TTS audio files
AWS_S3_AUDIO_URL_EXPIRY — How long presigned URLs are valid (seconds). Default: 3600 (1 hour)
```
**On ECS (production):** AWS credentials are NOT needed — ECS uses an IAM role attached
to the task. Only needed locally and in GitHub Actions CI.

---

### Drug Database
```
INDIAN_MEDICINE_API_KEY  — Optional for prototype. Leave blank to use CSV fallback.
INDIAN_MEDICINE_API_URL  — IndianMedicineDatabase.com API endpoint
```
For the 3-day prototype, leave both blank. The drug lookup service falls back to
`data/drugs/top_medicines.csv` which has 500+ common medicines and requires no key.

---

### Analytics
```
POSTHOG_API_KEY  — From posthog.com (free tier: 1M events/month)
POSTHOG_HOST     — Leave as default unless self-hosting PostHog
```
PostHog tracks: documents processed per day, language distribution, error rates,
repeat users. Used to generate the B2B dashboard metrics.

---

### Session / Security
```
SESSION_TTL_SECONDS         — How long a user session lives in Redis without activity.
                              Default: 1800 (30 minutes). After this, state resets to IDLE.

VALIDATE_TWILIO_SIGNATURE   — IMPORTANT:
                              false  = skip signature check (use during local dev with ngrok)
                              true   = verify every request is genuinely from Twilio
                              Always set to true in staging and production.
```

---

### Feature Flags
These are the most useful settings during development:

```
ENABLE_AUDIO=false        — Skips Bhashini TTS entirely. Use on Day 1-2 while building
                            extraction and translation. Saves 5–10 seconds per test.

ENABLE_DRUG_LOOKUP=false  — Skips drug DB enrichment. Use when testing just the
                            GPT-4o extraction + translation flow.

ENABLE_INDICTRANS2=false  — IndicTrans2 fallback is a self-hosted model. Leave false
                            for the prototype. Enable in Week 2 when self-hosting.

ENABLE_ANALYTICS=true     — Set false in dev to avoid polluting PostHog with test data.
```

## Day 1 Recommended `.env` Settings

```
ENVIRONMENT=development
OPENAI_API_KEY=<your key>
TWILIO_ACCOUNT_SID=<your sid>
TWILIO_AUTH_TOKEN=<your token>
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
BHASHINI_API_KEY=          ← leave blank on Day 1
BHASHINI_USER_ID=          ← leave blank on Day 1
DATABASE_URL=postgresql+asyncpg://sehat:sehatpassword@postgres:5432/sehatsamjho
REDIS_URL=redis://redis:6379/0
AWS_ACCESS_KEY_ID=         ← leave blank on Day 1–5
AWS_SECRET_ACCESS_KEY=     ← leave blank on Day 1–5
VALIDATE_TWILIO_SIGNATURE=false
ENABLE_AUDIO=false         ← skip TTS while building core flow
ENABLE_DRUG_LOOKUP=false   ← skip drug lookup while building core flow
ENABLE_ANALYTICS=false     ← avoid polluting analytics with test events
```
