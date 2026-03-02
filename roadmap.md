# Roadmap — SehatSamjho: AI Medical Document Translator

**Prototype target**: End-to-end WhatsApp → prescription translation → audio reply.
**Budget**: $30–50 AWS (free tier + minimal paid).
**LLM (Vision)**: OpenAI GPT-4O Vision for prescription image extraction.
**LLM (Text)**: Anthropic Claude Sonnet 4.6 for translation and all text-based AI calls.
**Out of scope for prototype**: B2B React dashboard, IndicTrans2, ABDM integration.

---

## Tech Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Messaging | Twilio WhatsApp Business API | Webhook integration, image + audio support |
| Backend | Python 3.11 / FastAPI / uvicorn | Async, strong ecosystem, fast iteration |
| LLM (Vision / Extraction) | OpenAI GPT-4O Vision (`gpt-4o`) | Best-in-class medical image OCR + structured extraction |
| LLM (Translation / Text) | Anthropic Claude Sonnet 4.6 (`claude-sonnet-4-6`) | Superior multilingual translation + plain-language simplification |
| TTS | Bhashini TTS API | Free, 22 Indian languages, government-backed |
| Drug Database | Local CSV + Redis cache + IndianMedicineDB API fallback | 1000+ Indian medicines, <100ms lookups |
| Medical Glossary | Per-language JSON files + Redis (RAG injection) | Grounds Claude translation for medical accuracy |
| Database | PostgreSQL via SQLAlchemy async + asyncpg | Metadata/analytics only (zero PHI) |
| Cache / Sessions | Redis (aioredis) | WhatsApp session state + drug cache + glossary cache |
| Storage | AWS S3 (audio files only) | Presigned URLs, 24hr lifecycle, <500KB per file |
| Hosting | AWS EC2 t3.micro (Docker) | Free tier, 750 hrs/month |
| Config | pydantic-settings + .env | All secrets via environment, no hardcoded keys |
| Logging | Loguru | Structured logs with request_id, no PHI |
| Testing | pytest + pytest-asyncio + httpx | Async test suite, all external services mocked |
| Linting | Ruff (line length: 100) | Fast, opinionated formatting |

---

## AWS Budget

| Resource | Tier | Est. Monthly Cost |
|----------|------|-------------------|
| EC2 t3.micro | Free tier (750 hrs/month, 12 months) | $0 |
| RDS db.t3.micro PostgreSQL | Free tier (750 hrs/month, 20GB, 12 months) | $0 |
| S3 (audio files) | Free tier (5GB, 2K PUT, 20K GET/month) | $0 |
| Upstash Redis | Free tier (10K req/day, 256MB) | $0 |
| Elastic IP | Free when attached to running instance | $0 |
| Data transfer out | Free 1GB/month | ~$0–2 |
| OpenAI GPT-4O Vision | ~$0.005 per extraction (image + structured output) | ~$5 per 1000 docs |
| Anthropic Claude Sonnet 4.6 | ~$0.002 per translation call | ~$2 per 1000 docs |
| Twilio WhatsApp | Per-conversation fee | ~$1–5 during testing |
| **Total (prototype demo volume)** | | **~$8–15/month** |

Budget buffer of $15–35 available for overages or optional extras (e.g., Route 53 domain at $12/year).

---

## Spec Folder Convention

Each spec has a dedicated folder under `specs/`:

```
specs/
  spec-S1.1-dependency-declaration/
    spec.md        ← detailed specification
    checklist.md   ← implementation checklist / progress tracker
  spec-S1.2-developer-commands/
    spec.md
    checklist.md
  ...
```

---

## Phases Overview

| Phase | Name | Specs | Key Output |
|-------|------|-------|------------|
| 1 | Project Setup | 5 | Runnable skeleton app |
| 2 | Data Layer | 5 | DB + Redis + Pydantic models |
| 3 | WhatsApp Channel | 5 | Twilio send/receive helpers |
| 4 | Webhook State Machine | 6 | Full conversation flow |
| 5 | GPT-4O Vision Extraction | 5 | Vision → PrescriptionData |
| 6 | Medical Glossary | 4 | RAG context for translation |
| 7 | Translation | 5 | Plain-language output in patient language |
| 8 | Drug Lookup | 5 | Medicine enrichment |
| 9 | TTS & Audio Delivery | 5 | Bhashini audio → S3 → WhatsApp |
| 10 | Pipeline Integration | 5 | End-to-end wired pipeline |
| 11 | Infra & Seeding | 7 | Docker + data files + migrations |
| 12 | AWS Deployment | 7 | Live on EC2 with Twilio connected |
| 13 | QA & Handover | 5 | Validated prototype, documented |

---

## Phase 1 — Project Setup

Bootstraps the project: dependency declaration, environment config, app factory, security helper.
No external services connected yet. Output: `make local-dev` starts a healthy FastAPI server.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S1.1 | `specs/spec-S1.1-dependency-declaration/` | — | `pyproject.toml`, `.env.example` | Dependency declaration | Deps: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, redis (replaces aioredis), anthropic, openai, tenacity, loguru, httpx, boto3, pydantic-settings, twilio, python-multipart. Dev extras: pytest, pytest-asyncio, httpx, ruff, pytest-mock | done |
| S1.2 | `specs/spec-S1.2-developer-commands/` | — | `Makefile` | Developer commands | Targets: `venv`, `install`, `install-dev`, `local-dev`, `local-test`, `local-lint`, `local-migrate`, `seed`, `dev` (Docker), `test` (Docker), `migrate` (Docker) | done |
| S1.3 | `specs/spec-S1.3-pydantic-settings/` | S1.1 | `backend/app/core/config.py` | Settings via pydantic-settings | Fields: OPENAI_API_KEY, ANTHROPIC_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, BHASHINI_API_KEY, BHASHINI_USER_ID, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET, DATABASE_URL, REDIS_URL. All loaded from .env | done |
| S1.4 | `specs/spec-S1.4-fastapi-app-factory/` | S1.3 | `backend/app/main.py` | FastAPI app factory | Lifespan: connect DB + Redis on startup, disconnect on shutdown. Include routers (webhooks, dashboard stub). GET /health endpoint returning `{"status": "ok"}` | done |
| S1.5 | `specs/spec-S1.5-twilio-hmac/` | S1.3 | `backend/app/core/security.py` | Twilio HMAC verification | `validate_twilio_signature(request, token)` — validates X-Twilio-Signature header. Returns 403 on failure. Used as FastAPI dependency on webhook endpoint | done |

---

## Phase 2 — Data Layer

Async database + Redis connections, PostgreSQL table definitions (metadata only), and all Pydantic schemas used across the project.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S2.1 | `specs/spec-S2.1-async-sqlalchemy/` | S1.3, S1.4 | `backend/app/db/database.py` | Async SQLAlchemy engine | `create_async_engine`, `AsyncSessionLocal`, `Base`, `get_db()` FastAPI dependency. Connection pool: pool_size=5, max_overflow=10 | done |
| S2.2 | `specs/spec-S2.2-async-redis/` | S1.3, S1.4 | `backend/app/db/redis.py` | Async Redis client | `get_redis()` FastAPI dependency using aioredis. Connection pool. Ping on startup to verify | done |
| S2.3 | `specs/spec-S2.3-interaction-log-table/` | S2.1 | `backend/app/db/models.py` | PostgreSQL table: interaction_log | Columns: id (UUID), created_at, phone_hash (SHA-256 of phone, no raw number), language_code, doc_type, confidence_avg, latency_ms, status (enum: success/error/flagged), error_code. Zero PHI. | done |
| S2.4 | `specs/spec-S2.4-pydantic-models/` | S1.1 | `backend/app/models/schemas.py` | All Pydantic models | Models: MedicineEntry, PrescriptionData, DrugInfo, TranslationResult, WebhookPayload, SessionState (with SessionStatus enum: WAITING_FOR_LANGUAGE, WAITING_FOR_IMAGE, PROCESSING). Request/response models for all service calls | done |
| S2.5 | `specs/spec-S2.5-alembic-migrations/` | S2.1 | `backend/alembic/` | Alembic migrations setup | `alembic.ini` (script_location, prepend_sys_path=.), `env.py` (async engine, import Base from models), `script.py.mako` (standard template), initial migration generating `interaction_log` table | done |

---

## Phase 3 — WhatsApp Channel

All Twilio send/receive helpers. Stateless utilities — no session logic here, only raw messaging primitives.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S3.1 | `specs/spec-S3.1-supported-languages/` | S2.4 | `backend/app/services/whatsapp.py` | SUPPORTED_LANGUAGES | Dict mapping language code → `{name, display_name, bhashini_code}` for all 22 scheduled Indian languages. Hindi = "hi", Tamil = "ta", etc. | done |
| S3.2 | `specs/spec-S3.2-parse-language/` | S3.1 | `backend/app/services/whatsapp.py` | `parse_language_selection()` | Accepts user input (number 1–8, language code, or language name). Returns `(language_name, language_code)` tuple or `None` if unrecognised. Case-insensitive matching | done |
| S3.3 | `specs/spec-S3.3-send-text-message/` | S1.3 | `backend/app/services/whatsapp.py` | `send_text_message()` | Async wrapper: `asyncio.to_thread` around Twilio `messages.create()`. Params: to, body. Retry via tenacity (3 attempts, 2s backoff) on Twilio API errors | done |
| S3.4 | `specs/spec-S3.4-send-language-selection/` | S3.1, S3.3 | `backend/app/services/whatsapp.py` | `send_language_selection()` | Sends WhatsApp quick-reply buttons (max 3 per row) listing top 8 languages + "More" option. Uses Twilio ContentSid or manual button formatting | done |
| S3.5 | `specs/spec-S3.5-send-audio-message/` | S3.3 | `backend/app/services/whatsapp.py` | `send_audio_message()` | Send S3 presigned audio URL as Twilio WhatsApp media message. Params: to, media_url. Falls back to text-only if media fails | done |

---

## Phase 4 — Webhook State Machine

The central orchestration layer. Manages conversation sessions in Redis, routes incoming WhatsApp messages to handlers based on session state.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S4.1 | `specs/spec-S4.1-webhook-endpoint/` | S1.5, S2.2, S3.3 | `backend/app/api/webhooks.py` | Webhook router + POST endpoint | `POST /webhook/whatsapp`. Parses Twilio form body (Form data). Validates HMAC signature via S1.5. Extracts: From, Body, NumMedia, MediaUrl0, MediaContentType0 | done |
| S4.2 | `specs/spec-S4.2-dispatch/` | S4.1, S2.2, S2.4 | `backend/app/api/webhooks.py` | `_dispatch()` | Load session from Redis (key: `session:{phone}`). Route to handler based on SessionStatus. Default (new session) → welcome handler. TTL: 30 minutes per session | done |
| S4.3 | `specs/spec-S4.3-welcome-state/` | S4.2, S3.4 | `backend/app/api/webhooks.py` | `_handle_welcome_state()` | Send consent message + language selection buttons. Store `SessionState(status=WAITING_FOR_LANGUAGE)` in Redis. Return Twilio empty TwiML response | pending |
| S4.4 | `specs/spec-S4.4-language-state/` | S4.2, S3.3 | `backend/app/api/webhooks.py` | `_handle_language_state()` | Parse language from message body via S3.2. If valid: store language in session, set status=WAITING_FOR_IMAGE, send "Please send a photo of your prescription". If invalid: re-send language buttons | pending |
| S4.5 | `specs/spec-S4.5-image-state/` | S4.2, S3.3 | `backend/app/api/webhooks.py` | `_handle_image_state()` | Validate NumMedia > 0 and MediaContentType is image/*. Send "Translating your document, please wait 20–30 seconds..." acknowledgement. Trigger async pipeline (placeholder hook for Phase 10) | pending |
| S4.6 | `specs/spec-S4.6-log-interaction/` | S4.1, S2.1, S2.3 | `backend/app/api/webhooks.py` | `_log_interaction()` | Write one row to `interaction_log` table. Hash phone number (SHA-256). Never log raw phone, image content, or extracted text. Called at end of every successful pipeline run | pending |

---

## Phase 5 — GPT-4O Vision Extraction

Uses OpenAI GPT-4O Vision to extract structured medical data from prescription images. Returns a `PrescriptionData` object with per-field confidence scores.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S5.1 | `specs/spec-S5.1-openai-client/` | S1.3, S2.4 | `backend/app/services/extraction.py` | OpenAI async client init | `openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)`. Module-level singleton via `_get_client()` (lazy init, testable via mock) | pending |
| S5.2 | `specs/spec-S5.2-extraction-prompt/` | S5.1 | `backend/app/services/extraction.py` | `_build_extraction_prompt()` | System prompt: medical document reader persona, output structured JSON with confidence scores per field. Instruct GPT-4O to never guess low-confidence dosages as definitive. Output schema matches `PrescriptionData` | pending |
| S5.3 | `specs/spec-S5.3-gpt4o-vision-call/` | S5.1, S5.2 | `backend/app/services/extraction.py` | `_call_gpt4o_vision()` | Download image from MediaUrl (httpx async GET), base64 encode, pass to `client.chat.completions.create()` with image_url content block + system prompt. Model: `gpt-4o`. Max tokens: 1024 | pending |
| S5.4 | `specs/spec-S5.4-extract-prescription/` | S5.3, S2.4 | `backend/app/services/extraction.py` | `extract_prescription()` | Orchestrate: validate image URL → call GPT-4O → parse JSON response → validate as `PrescriptionData` → return. Public API for Phase 10 pipeline wiring | pending |
| S5.5 | `specs/spec-S5.5-extraction-errors/` | S5.4 | `backend/app/services/extraction.py` | Error taxonomy + retry | Custom exceptions: `NotMedicalDocumentError`, `ImageNotReadableError` (semantic, not retried). Transient OpenAI API errors: retry with tenacity (3 attempts, exponential backoff). Log all failures with request_id | pending |

---

## Phase 6 — Medical Glossary

Curated per-language mappings of medical terms → plain-language vernacular explanations. Loaded into Redis at startup. Injected as grounding context into the Claude translation prompt.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S6.1 | `specs/spec-S6.1-glossary-data/` | — | `data/glossary/{lang_code}.json` | Glossary data files | JSON files for: hi, ta, te, kn, bn, mr (top 6 by usage). Each entry: `{"term": "hypertension", "explanation": "high blood pressure — when the force of blood against artery walls is too high", "vernacular": "..."}`. ~100 terms per language for prototype | pending |
| S6.2 | `specs/spec-S6.2-glossary-loader/` | S2.2, S6.1 | `backend/app/services/glossary.py` | `GlossaryLoader` + `load_glossary()` | On startup (or `make seed`): read all JSON files, load into Redis as hash `glossary:{lang_code}`. Key = term (lowercase), value = JSON string of full entry | pending |
| S6.3 | `specs/spec-S6.3-lookup-terms/` | S6.2, S2.4 | `backend/app/services/glossary.py` | `lookup_terms()` | Given a set of medical terms (from PrescriptionData) and a language_code → batch Redis HGET → return list of matching `GlossaryEntry` objects | pending |
| S6.4 | `specs/spec-S6.4-format-glossary/` | S6.3 | `backend/app/services/glossary.py` | `format_glossary_context()` | Format matched glossary entries as a structured string block: `"Term: X → {language}: Y"`. Returned string injected into Claude translation system prompt. Max ~500 tokens of context | pending |

---

## Phase 7 — Translation

Uses Anthropic Claude Sonnet 4.6 to simplify medical jargon and translate into the patient's chosen language. Glossary context from Phase 6 grounds the output. Output is `TranslationResult` with full text + per-medicine summaries.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S7.1 | `specs/spec-S7.1-anthropic-client/` | S1.3 | `backend/app/services/translation.py` | Anthropic async client + prompt templates | `anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)`. Module-level singleton via `_get_client()` (lazy init, testable via mock). Store system + user prompt templates as module-level constants | pending |
| S7.2 | `specs/spec-S7.2-system-prompt/` | S7.1 | `backend/app/services/translation.py` | `_build_system_prompt()` | Persona: caring health educator. Rules: explain not translate, preserve drug names + dosages in English, never add clinical advice, flag low-confidence items with ⚠️, keep output ≤300 words, add disclaimer at end. Injected with glossary_context block | pending |
| S7.3 | `specs/spec-S7.3-user-prompt/` | S7.1, S2.4 | `backend/app/services/translation.py` | `_build_user_prompt()` | Serialize `PrescriptionData` + `DrugInfo` list + `glossary_context` into structured user turn. Language target in prompt header. Low-confidence fields explicitly labelled | pending |
| S7.4 | `specs/spec-S7.4-translate/` | S7.2, S7.3, S5.5 | `backend/app/services/translation.py` | `simplify_and_translate()` | Call `client.messages.create()` with system + user prompts. Model: `claude-sonnet-4-6`. Parse response into `TranslationResult` (translated_text, per_medicine_summaries, disclaimer). Public API for Phase 10 | pending |
| S7.5 | `specs/spec-S7.5-translation-errors/` | S7.4 | `backend/app/services/translation.py` | Retry + error handling | Tenacity retry on transient Anthropic errors (3 attempts). `TranslationError` raised on parse failure or empty response. Log with request_id and language_code | pending |

---

## Phase 8 — Drug Lookup

Matches medicine names from extracted prescriptions against a local CSV cache (Redis) and IndianMedicineDB API as fallback. Returns enriched `DrugInfo` for each medicine.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S8.1 | `specs/spec-S8.1-drug-csv/` | — | `data/drugs/medicines.csv` | Drug database CSV | Columns: brand_name, generic_name, therapeutic_class, purpose_en, side_effects_en, timing_instructions, known_interactions. ~1000 most-prescribed Indian medicines. Source: public domain / OpenFDA-equivalent Indian data | pending |
| S8.2 | `specs/spec-S8.2-load-drug-csv/` | S2.2, S8.1 | `backend/app/services/drug_lookup.py` | `load_drug_csv()` | Read CSV, normalize brand + generic names (lowercase, strip). Load into Redis as hash `drugs:{brand_name_normalized}` and `drugs:{generic_name_normalized}`. Called by `make seed` | pending |
| S8.3 | `specs/spec-S8.3-lookup-drug/` | S8.2, S2.4 | `backend/app/services/drug_lookup.py` | `lookup_drug()` | Redis HGET on normalized name → return `DrugInfo` if found. Cache miss → call IndianMedicineDB API (GET with retry). Cache API result for 7 days. Return `DrugInfo` or `None` if not found | pending |
| S8.4 | `specs/spec-S8.4-enrich-prescription/` | S8.3, S2.4 | `backend/app/services/drug_lookup.py` | `enrich_prescription()` | For each `MedicineEntry` in `PrescriptionData` → `lookup_drug()` → collect `DrugInfo` list. Run lookups concurrently with `asyncio.gather`. Return `List[DrugInfo]` (aligned with medicines list) | pending |
| S8.5 | `specs/spec-S8.5-indian-medicine-api/` | S8.3 | `backend/app/services/drug_lookup.py` | IndianMedicineDB API client | `_call_indianmedicinedb()`: httpx async GET to IndianMedicineDatabase.com API. Parse JSON response. Tenacity retry (3 attempts). Return normalized `DrugInfo` or `None` on 404/timeout | pending |

---

## Phase 9 — TTS & Audio Delivery

Calls Bhashini TTS to generate audio from the translated text. Uploads to S3. Returns a presigned URL delivered to the patient as a WhatsApp voice message.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S9.1 | `specs/spec-S9.1-bhashini-client/` | S1.3 | `backend/app/services/tts.py` | Bhashini TTS API client | `_call_bhashini()`: POST to Bhashini pipeline inference endpoint. Payload: `{pipelineTasks: [{taskType: "tts", config: {language: {sourceLanguage: lang_code}, gender: "female"}}], inputData: {input: [{source: text}]}}`. Returns audio bytes (base64 decoded) | pending |
| S9.2 | `specs/spec-S9.2-text-to-speech/` | S9.1 | `backend/app/services/tts.py` | `text_to_speech()` | Call `_call_bhashini()` with translated_text + language_code. Validate audio bytes (non-empty, reasonable size). Return audio bytes. Tenacity retry on Bhashini API errors | pending |
| S9.3 | `specs/spec-S9.3-s3-upload/` | S1.3, S9.2 | `backend/app/services/tts.py` | `_upload_to_s3()` | `boto3.client("s3").put_object()` wrapped in `asyncio.to_thread`. Key: `audio/{uuid4()}.ogg`. ContentType: `audio/ogg`. Set S3 object expiry metadata. Return presigned URL with 3600s expiry | pending |
| S9.4 | `specs/spec-S9.4-audio-delivery/` | S9.2, S9.3 | `backend/app/services/tts.py` | `generate_and_deliver_audio()` | Orchestrate: `text_to_speech()` → `_upload_to_s3()` → return presigned URL. Public API for Phase 10 | pending |
| S9.5 | `specs/spec-S9.5-graceful-degradation/` | S9.4 | `backend/app/services/tts.py` | Graceful degradation | If Bhashini fails after retries or S3 upload fails: log warning, return `None`. Caller (Phase 10) handles `None` by sending text-only reply with note: "Audio not available, please read the text below." Never block the text response | pending |

---

## Phase 10 — Pipeline Integration

Wires all services (extraction → drug lookup → glossary → translation → TTS → send) into the webhook image handler. Adds response formatting and error handling for the patient-facing output.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S10.1 | `specs/spec-S10.1-pipeline-wiring/` | S4.5, S5.4, S6.3, S7.4, S8.4, S9.4 | `backend/app/api/webhooks.py` | `_handle_image_state()` full pipeline | Replace Phase 4 placeholder: call extraction (GPT-4O) → enrich → glossary lookup → translate (Claude) → TTS. All steps in sequence. Pass request_id (UUID) through all service calls for log correlation | pending |
| S10.2 | `specs/spec-S10.2-format-reply/` | S10.1, S2.4 | `backend/app/api/webhooks.py` | `_format_reply()` | Build WhatsApp text body: greeting, per-medicine cards (name EN + purpose in language + dosage), low-confidence warnings (⚠️), disclaimer. Max 1600 chars (WhatsApp message limit) | pending |
| S10.3 | `specs/spec-S10.3-format-audio-text/` | S7.4 | `backend/app/api/webhooks.py` | `_format_audio_text()` | Produce a clean spoken version of the summary (no emoji, no markdown, simpler sentence structure) for Bhashini TTS input | pending |
| S10.4 | `specs/spec-S10.4-pipeline-errors/` | S10.1 | `backend/app/api/webhooks.py` | `_handle_pipeline_error()` | Map exception types to patient-friendly WhatsApp messages. `NotMedicalDocumentError` → "This doesn't appear to be a medical document." `ImageNotReadableError` → "We couldn't read this clearly, please try better lighting." Generic error → "Something went wrong, please try again." | pending |
| S10.5 | `specs/spec-S10.5-pipeline-integration-test/` | S10.1, S10.2, S10.3, S10.4 | `backend/tests/api/test_pipeline.py` | Integration test: full pipeline | Mock all external services (OpenAI, Anthropic, Bhashini, S3, Twilio, Redis, DB). Send a fake WhatsApp image webhook. Assert: correct Twilio send calls, correct log entry, correct session state cleanup | pending |

---

## Phase 11 — Infra & Seeding

Docker setup for local dev and production. Drug CSV and glossary JSON data files. Seed script to load data into Redis. Alembic migration run command.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S11.1 | `specs/spec-S11.1-dockerfile/` | S1.1 | `backend/Dockerfile` | Multi-stage Dockerfile | Stage 1 (base): Python 3.11-slim, install uv, copy pyproject.toml, `uv pip install`. Stage 2 (dev): add pytest + ruff. Stage 3 (prod): copy app, non-root user, uvicorn CMD. Build context: repo root (not ./backend) | pending |
| S11.2 | `specs/spec-S11.2-docker-compose-dev/` | S11.1 | `docker-compose.yml` | Local dev stack | Services: postgres (postgres:15), redis (redis:7), app (build from Dockerfile dev stage). Volumes for postgres data. Env from .env file | pending |
| S11.3 | `specs/spec-S11.3-docker-compose-prod/` | S11.1 | `docker-compose.prod.yml` | Prod overrides | Override app image to prod stage. No local postgres/redis — use DATABASE_URL (RDS) and REDIS_URL (Upstash) from environment. Expose port 8000 | pending |
| S11.4 | `specs/spec-S11.4-dockerignore/` | — | `.dockerignore` | Docker ignore rules | Exclude: `.venv`, `data/*.csv` (large), `.env`, `notebooks/`, `docs/`, `**/__pycache__`, `*.pyc`, `.git` | pending |
| S11.5 | `specs/spec-S11.5-drug-csv-data/` | S8.1 | `data/drugs/medicines.csv` | Drug database CSV (data file) | 1000 most-prescribed Indian medicines. Columns: brand_name, generic_name, therapeutic_class, purpose_en, side_effects_en, timing_instructions, known_interactions. Manually curated or sourced from open datasets | pending |
| S11.6 | `specs/spec-S11.6-glossary-data-files/` | S6.1 | `data/glossary/*.json` | Glossary JSON files (data files) | Files: hi.json, ta.json, te.json, kn.json, bn.json, mr.json. ~100 entries each. Term → explanation + vernacular mapping | pending |
| S11.7 | `specs/spec-S11.7-seed-script/` | S8.2, S6.2, S2.5 | `backend/scripts/seed.py` + `Makefile` | `make seed` command | Load medicines.csv into Redis. Load all glossary JSON files into Redis. Run as: `python backend/scripts/seed.py`. Also runnable inside Docker via `make seed` target | pending |

---

## Phase 12 — AWS Deployment

Provision free-tier AWS infrastructure, deploy the Docker container, connect to Twilio, and run migrations + seed on the live environment.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S12.1 | `specs/spec-S12.1-ec2-setup/` | S11.1, S11.3 | AWS Console / docs | EC2 t3.micro setup | Region: ap-south-1 (Mumbai). AMI: Ubuntu 22.04 LTS. Install Docker + docker compose plugin. Security groups: inbound 80 (HTTP), 443 (HTTPS), 22 (SSH from your IP only). Assign Elastic IP | pending |
| S12.2 | `specs/spec-S12.2-rds-setup/` | S12.1 | AWS Console / docs | RDS db.t3.micro PostgreSQL | Same VPC as EC2. Security group: allow port 5432 from EC2 security group only. DB: sehatsamjho. User: ssadmin. Enable automated backups (7 days). 20GB gp2 storage | pending |
| S12.3 | `specs/spec-S12.3-s3-bucket/` | S12.1 | AWS Console / docs | S3 bucket setup | Bucket: sehatsamjho-audio-{account_id}. Region: ap-south-1. Block all public access. Lifecycle rule: delete objects with prefix `audio/` after 24 hours. CORS not needed (presigned URLs only) | pending |
| S12.4 | `specs/spec-S12.4-iam-role/` | S12.1, S12.3 | AWS Console / IAM | IAM role for EC2 | EC2 instance profile role. Policy: S3 PutObject + GetObject + DeleteObject on `sehatsamjho-audio-*` bucket only. No other permissions. Attach role to EC2 instance (no access keys needed on server) | pending |
| S12.5 | `specs/spec-S12.5-upstash-redis/` | — | Upstash Console / docs | Upstash Redis setup | Create free Upstash Redis database in ap-south-1. Copy REST URL + token to `.env.prod` as REDIS_URL. 256MB / 10K req/day — sufficient for prototype | pending |
| S12.6 | `specs/spec-S12.6-deploy-ec2/` | S12.1, S12.2, S12.3, S12.4, S12.5, S11.3 | EC2: `/app/.env` | Deploy to EC2 | SSH to EC2. Clone repo. Create `.env` with all prod secrets. `docker compose -f docker-compose.prod.yml up -d`. Run: `docker compose exec app alembic upgrade head` then `docker compose exec app python backend/scripts/seed.py` | pending |
| S12.7 | `specs/spec-S12.7-twilio-webhook/` | S12.6, S1.5 | Twilio Console | Twilio webhook URL update | Set WhatsApp Sandbox (or production) webhook URL to `http://{EC2_IP}/webhook/whatsapp`. Method: POST. Verify HMAC signature validation works by sending a test WhatsApp message | pending |

---

## Phase 13 — QA & Handover

End-to-end validation with real prescriptions. Latency profiling. Edge case verification. Documentation for handover.

| Spec | Spec Location | Depends On | Location | Feature | Notes | Status |
|------|--------------|-----------|----------|---------|-------|--------|
| S13.1 | `specs/spec-S13.1-hindi-e2e-test/` | S12.7 | Manual test | Hindi end-to-end smoke test | Send a real printed prescription image via WhatsApp. Verify: language selection works, extraction is accurate, translation is plain-language Hindi, audio plays correctly in WhatsApp, disclaimer present | pending |
| S13.2 | `specs/spec-S13.2-tamil-e2e-test/` | S12.7 | Manual test | Tamil end-to-end test | Repeat with Tamil. Validate: Bhashini TTS sounds natural, drug lookup finds medicines, low-confidence items flagged correctly | pending |
| S13.3 | `specs/spec-S13.3-edge-cases/` | S12.7 | Manual test | Edge case validation | Test: blurry/unreadable image, non-medical image (selfie), lab report (not prescription), handwritten prescription. Verify graceful error messages in each case | pending |
| S13.4 | `specs/spec-S13.4-latency-profiling/` | S12.7 | Timing + Loguru logs | Latency profiling | Target: full pipeline < 30 seconds (image received → audio reply sent). Measure each step: GPT-4O extraction, drug lookup, Claude translation, Bhashini TTS, S3 upload, Twilio send. Log timing per step | pending |
| S13.5 | `specs/spec-S13.5-documentation/` | S10.5 | `README.md`, `docs/` | Documentation | README: local setup (make venv, make install-dev, make local-dev), running tests, environment variables. Deployment guide: step-by-step Phase 12 instructions. .env.example with all required keys and comments | pending |

---

## Master Spec Index

| Spec | Phase | Location | Feature | Spec Location | Status |
|------|-------|----------|---------|--------------|--------|
| S1.1 | Project Setup | `pyproject.toml`, `.env.example` | Dependency declaration | `specs/spec-S1.1-dependency-declaration/` | done |
| S1.2 | Project Setup | `Makefile` | Developer commands | `specs/spec-S1.2-developer-commands/` | done |
| S1.3 | Project Setup | `backend/app/core/config.py` | pydantic-settings config | `specs/spec-S1.3-pydantic-settings/` | done |
| S1.4 | Project Setup | `backend/app/main.py` | FastAPI app factory | `specs/spec-S1.4-fastapi-app-factory/` | done |
| S1.5 | Project Setup | `backend/app/core/security.py` | Twilio HMAC verification | `specs/spec-S1.5-twilio-hmac/` | done |
| S2.1 | Data Layer | `backend/app/db/database.py` | Async SQLAlchemy engine | `specs/spec-S2.1-async-sqlalchemy/` | done |
| S2.2 | Data Layer | `backend/app/db/redis.py` | Async Redis client | `specs/spec-S2.2-async-redis/` | done |
| S2.3 | Data Layer | `backend/app/db/models.py` | interaction_log table | `specs/spec-S2.3-interaction-log-table/` | done |
| S2.4 | Data Layer | `backend/app/models/schemas.py` | All Pydantic models | `specs/spec-S2.4-pydantic-models/` | done |
| S2.5 | Data Layer | `backend/alembic/` | Alembic migrations setup | `specs/spec-S2.5-alembic-migrations/` | done |
| S3.1 | WhatsApp Channel | `backend/app/services/whatsapp.py` | SUPPORTED_LANGUAGES | `specs/spec-S3.1-supported-languages/` | done |
| S3.2 | WhatsApp Channel | `backend/app/services/whatsapp.py` | parse_language_selection() | `specs/spec-S3.2-parse-language/` | done |
| S3.3 | WhatsApp Channel | `backend/app/services/whatsapp.py` | send_text_message() | `specs/spec-S3.3-send-text-message/` | done |
| S3.4 | WhatsApp Channel | `backend/app/services/whatsapp.py` | send_language_selection() | `specs/spec-S3.4-send-language-selection/` | done |
| S3.5 | WhatsApp Channel | `backend/app/services/whatsapp.py` | send_audio_message() | `specs/spec-S3.5-send-audio-message/` | done |
| S4.1 | Webhook State Machine | `backend/app/api/webhooks.py` | Webhook router + POST endpoint | `specs/spec-S4.1-webhook-endpoint/` | done |
| S4.2 | Webhook State Machine | `backend/app/api/webhooks.py` | _dispatch() | `specs/spec-S4.2-dispatch/` | done |
| S4.3 | Webhook State Machine | `backend/app/api/webhooks.py` | _handle_welcome_state() | `specs/spec-S4.3-welcome-state/` | pending |
| S4.4 | Webhook State Machine | `backend/app/api/webhooks.py` | _handle_language_state() | `specs/spec-S4.4-language-state/` | pending |
| S4.5 | Webhook State Machine | `backend/app/api/webhooks.py` | _handle_image_state() | `specs/spec-S4.5-image-state/` | pending |
| S4.6 | Webhook State Machine | `backend/app/api/webhooks.py` | _log_interaction() | `specs/spec-S4.6-log-interaction/` | pending |
| S5.1 | GPT-4O Vision Extraction | `backend/app/services/extraction.py` | OpenAI async client | `specs/spec-S5.1-openai-client/` | pending |
| S5.2 | GPT-4O Vision Extraction | `backend/app/services/extraction.py` | _build_extraction_prompt() | `specs/spec-S5.2-extraction-prompt/` | pending |
| S5.3 | GPT-4O Vision Extraction | `backend/app/services/extraction.py` | _call_gpt4o_vision() | `specs/spec-S5.3-gpt4o-vision-call/` | pending |
| S5.4 | GPT-4O Vision Extraction | `backend/app/services/extraction.py` | extract_prescription() | `specs/spec-S5.4-extract-prescription/` | pending |
| S5.5 | GPT-4O Vision Extraction | `backend/app/services/extraction.py` | Error taxonomy + retry | `specs/spec-S5.5-extraction-errors/` | pending |
| S6.1 | Medical Glossary | `data/glossary/{lang}.json` | Glossary data files | `specs/spec-S6.1-glossary-data/` | pending |
| S6.2 | Medical Glossary | `backend/app/services/glossary.py` | GlossaryLoader + load_glossary() | `specs/spec-S6.2-glossary-loader/` | pending |
| S6.3 | Medical Glossary | `backend/app/services/glossary.py` | lookup_terms() | `specs/spec-S6.3-lookup-terms/` | pending |
| S6.4 | Medical Glossary | `backend/app/services/glossary.py` | format_glossary_context() | `specs/spec-S6.4-format-glossary/` | pending |
| S7.1 | Translation | `backend/app/services/translation.py` | Anthropic client + prompts | `specs/spec-S7.1-anthropic-client/` | pending |
| S7.2 | Translation | `backend/app/services/translation.py` | _build_system_prompt() | `specs/spec-S7.2-system-prompt/` | pending |
| S7.3 | Translation | `backend/app/services/translation.py` | _build_user_prompt() | `specs/spec-S7.3-user-prompt/` | pending |
| S7.4 | Translation | `backend/app/services/translation.py` | simplify_and_translate() | `specs/spec-S7.4-translate/` | pending |
| S7.5 | Translation | `backend/app/services/translation.py` | Retry + error handling | `specs/spec-S7.5-translation-errors/` | pending |
| S8.1 | Drug Lookup | `data/drugs/medicines.csv` | Drug database CSV | `specs/spec-S8.1-drug-csv/` | pending |
| S8.2 | Drug Lookup | `backend/app/services/drug_lookup.py` | load_drug_csv() | `specs/spec-S8.2-load-drug-csv/` | pending |
| S8.3 | Drug Lookup | `backend/app/services/drug_lookup.py` | lookup_drug() | `specs/spec-S8.3-lookup-drug/` | pending |
| S8.4 | Drug Lookup | `backend/app/services/drug_lookup.py` | enrich_prescription() | `specs/spec-S8.4-enrich-prescription/` | pending |
| S8.5 | Drug Lookup | `backend/app/services/drug_lookup.py` | IndianMedicineDB API client | `specs/spec-S8.5-indian-medicine-api/` | pending |
| S9.1 | TTS & Audio | `backend/app/services/tts.py` | Bhashini TTS API client | `specs/spec-S9.1-bhashini-client/` | pending |
| S9.2 | TTS & Audio | `backend/app/services/tts.py` | text_to_speech() | `specs/spec-S9.2-text-to-speech/` | pending |
| S9.3 | TTS & Audio | `backend/app/services/tts.py` | _upload_to_s3() | `specs/spec-S9.3-s3-upload/` | pending |
| S9.4 | TTS & Audio | `backend/app/services/tts.py` | generate_and_deliver_audio() | `specs/spec-S9.4-audio-delivery/` | pending |
| S9.5 | TTS & Audio | `backend/app/services/tts.py` | Graceful degradation | `specs/spec-S9.5-graceful-degradation/` | pending |
| S10.1 | Pipeline Integration | `backend/app/api/webhooks.py` | Full pipeline wiring | `specs/spec-S10.1-pipeline-wiring/` | pending |
| S10.2 | Pipeline Integration | `backend/app/api/webhooks.py` | _format_reply() | `specs/spec-S10.2-format-reply/` | pending |
| S10.3 | Pipeline Integration | `backend/app/api/webhooks.py` | _format_audio_text() | `specs/spec-S10.3-format-audio-text/` | pending |
| S10.4 | Pipeline Integration | `backend/app/api/webhooks.py` | _handle_pipeline_error() | `specs/spec-S10.4-pipeline-errors/` | pending |
| S10.5 | Pipeline Integration | `backend/tests/api/test_pipeline.py` | Integration test: full pipeline | `specs/spec-S10.5-pipeline-integration-test/` | pending |
| S11.1 | Infra & Seeding | `backend/Dockerfile` | Multi-stage Dockerfile | `specs/spec-S11.1-dockerfile/` | pending |
| S11.2 | Infra & Seeding | `docker-compose.yml` | Local dev stack | `specs/spec-S11.2-docker-compose-dev/` | pending |
| S11.3 | Infra & Seeding | `docker-compose.prod.yml` | Prod overrides | `specs/spec-S11.3-docker-compose-prod/` | pending |
| S11.4 | Infra & Seeding | `.dockerignore` | Docker ignore rules | `specs/spec-S11.4-dockerignore/` | pending |
| S11.5 | Infra & Seeding | `data/drugs/medicines.csv` | Drug database CSV (data file) | `specs/spec-S11.5-drug-csv-data/` | pending |
| S11.6 | Infra & Seeding | `data/glossary/*.json` | Glossary JSON files | `specs/spec-S11.6-glossary-data-files/` | pending |
| S11.7 | Infra & Seeding | `backend/scripts/seed.py` | make seed command | `specs/spec-S11.7-seed-script/` | pending |
| S12.1 | AWS Deployment | AWS Console | EC2 t3.micro setup | `specs/spec-S12.1-ec2-setup/` | pending |
| S12.2 | AWS Deployment | AWS Console | RDS db.t3.micro PostgreSQL | `specs/spec-S12.2-rds-setup/` | pending |
| S12.3 | AWS Deployment | AWS Console | S3 bucket setup | `specs/spec-S12.3-s3-bucket/` | pending |
| S12.4 | AWS Deployment | AWS IAM | IAM role for EC2 | `specs/spec-S12.4-iam-role/` | pending |
| S12.5 | AWS Deployment | Upstash Console | Upstash Redis free tier | `specs/spec-S12.5-upstash-redis/` | pending |
| S12.6 | AWS Deployment | EC2 shell | Deploy to EC2 | `specs/spec-S12.6-deploy-ec2/` | pending |
| S12.7 | AWS Deployment | Twilio Console | Twilio webhook URL update | `specs/spec-S12.7-twilio-webhook/` | pending |
| S13.1 | QA & Handover | Manual test | Hindi end-to-end smoke test | `specs/spec-S13.1-hindi-e2e-test/` | pending |
| S13.2 | QA & Handover | Manual test | Tamil end-to-end test | `specs/spec-S13.2-tamil-e2e-test/` | pending |
| S13.3 | QA & Handover | Manual test | Edge case validation | `specs/spec-S13.3-edge-cases/` | pending |
| S13.4 | QA & Handover | Logs | Latency profiling | `specs/spec-S13.4-latency-profiling/` | pending |
| S13.5 | QA & Handover | `README.md` | Documentation | `specs/spec-S13.5-documentation/` | pending |
