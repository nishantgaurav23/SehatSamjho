# SehatSamjho — Prototype Checklist

**Project:** AI Medical Document Translator via WhatsApp
**Timeline:** Feb 26 – Mar 4, 2026 (7 days)
**Working Prototype Target:** Feb 28, 2026 (Day 3)
**AWS-Ready Target:** Mar 4, 2026 (Day 7)

## Team
| Developer | Branch |
|-----------|--------|
| Nishant | `feature/sehatsamjo-nishant` |
| Dev 2 | `feature/sehatsamjo-dev2` ← create this |

## Legend
- `[ ]` Pending
- `[x]` Done
- `[~]` In Progress
- `[!]` Blocked

---

## DAY 1 — Feb 26 | Infrastructure & Core Integration

### Environment Setup
- [ ] Clone repo and switch to your branch
- [ ] Copy `.env.example` → `.env` and fill all keys
- [ ] `make up` — PostgreSQL + Redis start in Docker
- [ ] `make migrate` — DB tables created
- [ ] Python venv: `cd backend && pip install -r requirements.txt`
- [ ] Verify: `make dev` starts FastAPI at http://localhost:8000
- [ ] Verify: http://localhost:8000/health returns `{"status":"ok"}`

### API Keys to Get (Day 1)
- [ ] **OpenAI** — GPT-4o API key (platform.openai.com)
- [ ] **Twilio** — Account SID + Auth Token + WhatsApp Sandbox number (console.twilio.com)
- [ ] **Bhashini** — Register at bhashini.gov.in → get API key + User ID
- [ ] **PostHog** — API key (posthog.com, free tier)
- [ ] **IndianMedicineDatabase** — Request API access OR use bundled CSV

### WhatsApp Webhook Setup
- [ ] Run `ngrok http 8000` to get public tunnel URL
- [ ] Set Twilio sandbox webhook URL: `https://<ngrok>/webhook/whatsapp`
- [ ] Send "Hi" to Twilio sandbox number → verify it hits `/webhook/whatsapp`
- [ ] Send text message → receive text reply

### GPT-4o Vision
- [ ] Send a test prescription image URL to GPT-4o Vision API
- [ ] Verify structured JSON extraction (medicines, dosages, doctor info)
- [ ] Confidence scoring working (high/medium/low per field)
- [ ] Edge case: blurry image → returns low confidence

**Day 1 Exit Criteria:** FastAPI server receives WhatsApp image/text, responds with text.

---

## DAY 2 — Feb 27 | Translation + Audio + Drug Lookup

### WhatsApp State Machine
- [ ] `IDLE` → user sends "Hi" → bot responds with language quick-reply buttons
- [ ] `AWAITING_LANGUAGE` → user taps language → language stored in Redis → bot asks for document
- [ ] `AWAITING_DOCUMENT` → user sends image → bot processes
- [ ] `PROCESSING` → bot sends "Translating, please wait 20–30 seconds..."
- [ ] `IDLE` (reset) → bot sends text + audio response
- [ ] Timeout: session expires after 30 min inactivity
- [ ] Error path: user sends text during AWAITING_DOCUMENT → "Please send a photo"

### GPT-4o Simplification + Translation
- [ ] Hindi translation working end-to-end
- [ ] Output format: medicine name → purpose → dosage in plain language
- [ ] Drug names preserved in English alongside Hindi text
- [ ] Disclaimer appended: "यह एक सरलीकृत अनुवाद है..."
- [ ] Low-confidence items flagged with ⚠️

### Bhashini TTS
- [ ] Hindi TTS API call working → returns base64 audio
- [ ] Audio decoded and saved to temp file
- [ ] Audio compressed to < 500KB
- [ ] Audio uploaded to S3 (or served from temp URL)
- [ ] Audio sent as WhatsApp voice message via Twilio
- [ ] Test: Tamil TTS
- [ ] Test: Telugu TTS
- [ ] Test: Bengali TTS

### Drug Lookup
- [ ] `data/drugs/top_medicines.csv` loaded into Redis on startup
- [ ] Lookup by brand name and generic name (case-insensitive)
- [ ] Returns: generic name, uses, side effects, timing, interactions
- [ ] Handles: medicine not found gracefully
- [ ] `make seed` populates drug DB

### PostgreSQL Logging
- [ ] `translation_logs` table: timestamp, language, doc_type, confidence_avg, latency_ms, success
- [ ] Every translation request logged (no PHI stored)
- [ ] `/api/dashboard/stats` returns basic aggregates

**Day 2 Exit Criteria:** Send prescription photo → receive Hindi text + voice message within 30 seconds.

---

## DAY 3 — Feb 28 | Testing, Data & Polish

### End-to-End Test Suite
- [ ] Test 1: Printed English prescription → Hindi translation
- [ ] Test 2: Handwritten prescription (blurry) → confidence flags
- [ ] Test 3: Lab report → numerical values explained
- [ ] Test 4: Discharge summary → simplified summary
- [ ] Test 5: Non-medical image → rejection message
- [ ] Test 6: Tamil language end-to-end
- [ ] Test 7: Telugu language end-to-end
- [ ] Test 8: Bengali language end-to-end
- [ ] Latency: measure average response time (target < 30s)

### Data Gathering (Critical)
- [ ] `python scripts/fetch_drug_data.py` — downloads/builds drug database
- [ ] Verify 500+ medicines in `top_medicines.csv`
- [ ] `data/glossary/hindi_terms.json` — 100+ medical terms with Hindi explanations
- [ ] Prescription abbreviations added: OD, BD, TDS, QID, HS, AC, PC, SOS, PRN, STAT
- [ ] Common diagnoses in Hindi: diabetes, hypertension, thyroid, fever, infection, etc.
- [ ] Glossary injected into GPT-4o translation prompt → test improvement

### Error Handling
- [ ] Blurry image: "We couldn't read this clearly. Please try again with better lighting."
- [ ] Non-medical doc: "This doesn't appear to be a medical document."
- [ ] OpenAI timeout (> 30s): "Taking longer than usual, please try again."
- [ ] Bhashini API down: fallback to text-only response
- [ ] Rate limiting: queue retries with exponential backoff
- [ ] Twilio delivery failure: log + alert

### Docker & Local Dev
- [ ] `docker-compose up` starts api + postgres + redis cleanly
- [ ] `make dev` hot-reloads on file changes
- [ ] `make test` runs all tests
- [ ] `make lint` passes
- [ ] All secrets in `.env`, none hardcoded

**Day 3 Exit Criteria:** Fully working prototype. 5 core features working. Docker-ready. Demo-able.

---

## DAY 4–5 — Mar 1–2 | Language Expansion & Hardening

### Language Expansion (6 languages)
- [ ] Tamil (ta) — full flow
- [ ] Telugu (te) — full flow
- [ ] Bengali (bn) — full flow
- [ ] Marathi (mr) — full flow
- [ ] Gujarati (gu) — full flow
- [ ] Malayalam (ml) — full flow

### Medical Glossary (per language)
- [ ] Hindi (hi): 200+ terms ← primary focus
- [ ] Tamil (ta): 50+ terms
- [ ] Telugu (te): 50+ terms
- [ ] Bengali (bn): 50+ terms
- [ ] Common lab test names in all 6 languages
- [ ] Common diagnoses in all 6 languages
- [ ] Prescription abbreviation explanations in all 6 languages

### Performance Targets
- [ ] Average response time < 30s (p50), < 45s (p95)
- [ ] Audio file size < 500KB for all languages
- [ ] Drug lookup Redis hit rate > 70% (after warm-up)
- [ ] PostgreSQL query time < 100ms

### Quality Improvements
- [ ] IndicTrans2 fallback integrated (when GPT-4o quality is low)
- [ ] Cross-check: flag when GPT-4o and IndicTrans2 translations differ significantly
- [ ] Medical glossary reduces mistranslations (validate with bilingual tester)

---

## DAY 6 — Mar 3 | AWS Infrastructure

### AWS Setup (ap-south-1 Mumbai)
- [ ] Create ECR repository: `sehatsamjho/api`
- [ ] Create ECS cluster: `sehatsamjho-cluster`
- [ ] Create VPC + subnets (or use default)
- [ ] Create security group: allow 80/443 inbound, 8000 internal
- [ ] Create RDS PostgreSQL: `db.t3.micro`, `sehatsamjho-staging`
- [ ] Create ElastiCache Redis: `cache.t3.micro`, `sehatsamjho-redis`
- [ ] Create S3 bucket: `sehatsamjho-audio-{env}` (private)
- [ ] Create ALB: `sehatsamjho-alb`
- [ ] Create ECS task definition (see `infra/ecs-task-definition.json`)
- [ ] Create ECS service with 1 desired task
- [ ] Create IAM role for ECS: S3 read/write, ECR pull, SSM Parameter Store

### GitHub Actions CI/CD
- [ ] Add GitHub secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- [ ] Add GitHub secrets: all API keys (see `.env.example`)
- [ ] CI workflow passes: `lint → test → build`
- [ ] Deploy workflow: push to `main` → build image → push ECR → update ECS
- [ ] Branch protection: require CI pass on PRs to `main`

### Staging Validation
- [ ] ECS task running → health check passing
- [ ] Database migrations run on staging
- [ ] Twilio webhook URL updated to ALB DNS
- [ ] Test full flow on staging (send prescription → receive response)

---

## DAY 7 — Mar 4 | Final Testing & Handover

### Staging Integration Tests
- [ ] 10 test translations on AWS staging (all passing)
- [ ] Latency on AWS < 30s
- [ ] Audio delivery working through S3 presigned URLs
- [ ] Error rates < 5%
- [ ] Zero PHI in DB (verify logs contain only metadata)

### Documentation
- [ ] `README.md` — setup, local dev, deployment instructions
- [ ] API docs at http://localhost:8000/docs (auto-generated)
- [ ] `infra/README.md` — AWS architecture and setup steps
- [ ] Prompt engineering decisions documented
- [ ] Known limitations documented

### Compliance Checklist
- [ ] Patient consent message at first interaction
- [ ] Disclaimer on every response (text + audio)
- [ ] Images purged from memory after processing
- [ ] No PHI in PostgreSQL logs
- [ ] TLS 1.3 on all HTTPS connections (ALB handles this)
- [ ] S3 bucket not public

### Handover
- [ ] All secrets in shared password manager (1Password / Bitwarden)
- [ ] PR from `feature/sehatsamjo-nishant` → reviewed → merged to `main`
- [ ] PR from `feature/sehatsamjo-dev2` → reviewed → merged to `main`
- [ ] Demo recorded (screen + WhatsApp flow)
- [ ] Prototype review meeting scheduled

---

## Backlog (Post Day 7)

### B2B Dashboard (Week 2)
- [ ] React app in `frontend/`
- [ ] Translation volume over time
- [ ] Language distribution chart
- [ ] Document type breakdown
- [ ] Confidence score distribution
- [ ] Partner login (JWT auth)
- [ ] CSV data export

### Additional Integrations (Week 3+)
- [ ] IndicTrans2 self-hosted (AI4Bharat) for full offline fallback
- [ ] ABDM/ABHA integration (patient consent → health record pull)
- [ ] PostHog analytics: funnel tracking, retention
- [ ] Kiosk mode (tablet-optimized UI, no WhatsApp)

---

## API Keys Reference

| Service | Where to Get | Used In |
|---------|-------------|---------|
| OpenAI GPT-4o | platform.openai.com | Extraction + Translation |
| Twilio WhatsApp | console.twilio.com | Message send/receive |
| Bhashini | bhashini.gov.in (free) | Text-to-Speech |
| AWS | AWS Console | Storage + Deployment |
| PostHog | posthog.com | Analytics |
| IndianMedicineDB | indianmedicinedatabase.com | Drug Lookup (optional for prototype) |

## Architecture Quick Reference

```
Patient (WhatsApp)
    ↓ photo
Twilio → POST /webhook/whatsapp (FastAPI)
    → Redis: get user state + language
    → GPT-4o Vision: extract medicines/dosages (JSON + confidence)
    → GPT-4o LLM: simplify + translate to user's language
    → Drug DB (Redis/CSV): enrich each medicine
    → Bhashini TTS: text → audio (< 500KB)
    → S3: store audio (presigned URL)
    → Twilio: send text card + voice message to patient
    → PostgreSQL: log metadata (no PHI)
```

## Useful Commands

```bash
make dev          # Start local dev (hot reload)
make up           # Start all Docker services
make down         # Stop all services
make logs         # Follow API logs
make migrate      # Run DB migrations
make seed         # Seed drug database + glossary
make test         # Run test suite
make lint         # Lint Python code
make ngrok        # Start ngrok tunnel (for Twilio webhook)
make build-push   # Build + push Docker image to ECR
```
