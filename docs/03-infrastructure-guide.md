# Infrastructure Guide — SehatSamjho Backend

How every infrastructure file works, how they connect to each other,
how to run them, and how to send real data to verify they're working.

---

## 1. File Map and Integration

```
.env  ──────────────────────────────────────────────────────────────────────┐
                                                                             │
app/core/config.py          reads .env via pydantic-settings                │
  └── settings object ──────────────────────────────────────────────────────┘
        │  DATABASE_URL, TWILIO_*, OPENAI_*, etc.
        │
        ├──► app/db/database.py          creates the async DB engine + session factory
        │       │  engine                ──► alembic/env.py  (migrations)
        │       │  AsyncSessionLocal     ──► conftest.py     (test sessions)
        │       │  Base                  ──► app/db/models.py (ORM inherits this)
        │       └  get_db()              ──► api/webhooks.py, api/dashboard.py (Depends)
        │
        ├──► app/db/models.py            TranslationLog ORM table definition
        │       │  inherits Base from database.py
        │       └  alembic reads Base.metadata to autogenerate migration SQL
        │
        ├──► app/core/security.py        hash_phone() + verify_twilio_signature()
        │       └  used in api/webhooks.py for every incoming Twilio POST
        │
        └──► app/main.py                 FastAPI app entry point
                │  imports database.py   → DB startup check in lifespan
                │  imports api/webhooks  → POST /webhook/whatsapp
                └  imports api/dashboard → GET /dashboard/*
```

### File-by-file: what each file does and what it imports

| File | Imports from | Imported by |
|------|--------------|-------------|
| `core/config.py` | nothing (reads `.env`) | every other file |
| `db/database.py` | `core/config.py` | `main.py`, `alembic/env.py`, all routes, `conftest.py` |
| `db/models.py` | `db/database.py` (Base) | `alembic/env.py`, `api/webhooks.py`, `api/dashboard.py` |
| `models/schemas.py` | nothing (pure Pydantic) | `api/webhooks.py`, `api/dashboard.py`, all services |
| `core/security.py` | `core/config.py` | `api/webhooks.py` |
| `api/webhooks.py` | `db/database.py`, `db/models.py`, `models/schemas.py`, `core/security.py` | `main.py` |
| `api/dashboard.py` | `db/database.py`, `db/models.py`, `models/schemas.py` | `main.py` |
| `main.py` | `core/config.py`, `db/database.py`, `api/webhooks.py`, `api/dashboard.py` | uvicorn (entry point) |

---

## 2. Data Flow Through Infrastructure

```
HTTP POST /webhook/whatsapp
    │
    ▼
main.py                     FastAPI receives request
    │  app.include_router(webhooks.router)
    ▼
api/webhooks.py             Route handler (stub — Day 1 fills this)
    │  db: AsyncSession = Depends(get_db)    ← injects DB session
    │  verify_twilio_signature(url, params, sig)  ← HMAC check
    │  phone_hash = hash_phone(payload.From)      ← SHA-256, no PHI stored
    ▼
db/models.py                TranslationLog ORM row assembled
    │  request_id, phone_hash, language_code, latency_ms, ...
    ▼
db/database.py / get_db()   Commits row to PostgreSQL, closes session
    │
    ▼
PostgreSQL                  Row lives in translation_logs table
```

---

## 3. How Alembic Migrations Tie Together

```
app/db/models.py
    └── class TranslationLog(Base)     ← ORM definition

alembic/env.py
    ├── loads .env (dotenv)
    ├── imports settings.database_url  ← connection string
    ├── imports Base.metadata          ← knows about all ORM tables
    └── async_engine_from_config()     ← asyncpg driver

alembic/versions/
    └── 20260227_*_create_translation_logs_table.py   ← generated SQL

Command: alembic upgrade head
    → reads versions/, applies pending migrations → creates table in PostgreSQL
```

---

## 4. Test Infrastructure

```
tests/conftest.py
    ├── load_dotenv()                  reads .env before any app module imports
    ├── event_loop (session-scoped)    one asyncio loop shared across all tests
    │                                  required: asyncpg binds conns to their loop
    ├── reset_connection_pool          disposes engine pool before each test
    │                                  prevents stale connections between tests
    └── db_session (sync fixture)      opens AsyncSession, closes on session loop
                                       teardown runs via event_loop.run_until_complete()
                                       to avoid "Future attached to different loop" error

tests/db/test_database.py   → tests engine, session factory, get_db()
tests/db/test_models.py     → tests TranslationLog schema + live DB round-trips
tests/models/test_schemas.py → tests all Pydantic models (no DB needed)
tests/core/test_security.py → tests hash_phone + Twilio HMAC verification
tests/test_main.py          → tests /health endpoint, app metadata
```

---

## 5. Prerequisites

Before running anything, you need:

```bash
# 1. Python virtual environment
make venv                       # creates .venv at project root
source .venv/bin/activate       # activate it

# 2. Install dependencies
make install-dev                # installs all packages including pytest/ruff

# 3. Environment file
cp .env.example .env            # copy the template
# Edit .env and fill in at minimum:
#   OPENAI_API_KEY=sk-...
#   TWILIO_ACCOUNT_SID=AC...
#   TWILIO_AUTH_TOKEN=...
#   TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
#   DATABASE_URL=postgresql+asyncpg://sehat:sehatpassword@localhost:5435/sehatsamjho

# 4. Start PostgreSQL + Redis (Docker required)
make services                   # starts postgres on :5435 and redis on :6379
                                 # does NOT start the API container — run API locally

# 5. Run migrations (creates translation_logs table)
make local-migrate              # runs: alembic upgrade head
```

---

## 6. Running the Server

```bash
# Activate venv first (if not already active)
source .venv/bin/activate

# Start the dev server (hot-reload)
make local-dev
# → http://localhost:8000

# Verify it's alive
curl http://localhost:8000/health
# Expected: {"status": "ok", "env": "development"}

# Swagger UI (debug=True in .env)
open http://localhost:8000/docs
```

---

## 7. Running the Tests

```bash
source .venv/bin/activate

# Full suite (all 48 tests)
make local-test

# Individual test files
python -m pytest backend/tests/db/test_database.py -v
python -m pytest backend/tests/db/test_models.py -v
python -m pytest backend/tests/models/test_schemas.py -v
python -m pytest backend/tests/core/test_security.py -v
python -m pytest backend/tests/test_main.py -v

# Single test by name
python -m pytest backend/tests/db/test_models.py::test_insert_and_query -v

# Stop on first failure
python -m pytest backend/tests/ -x -v
```

**Prerequisites for live DB tests** (`test_database.py`, `test_models.py`):
- PostgreSQL running: `make services`
- Migrations applied: `make local-migrate`

---

## 8. Sending Test Data and Verifying Results

### 8a. Health check

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
# Expected:
# {
#     "status": "ok",
#     "env": "development"
# }
```

### 8b. Simulate a Twilio WhatsApp webhook POST

Twilio sends `application/x-www-form-urlencoded` to `/webhook/whatsapp`.
The stub router accepts any POST but returns nothing until Day 1 is implemented.

```bash
# Basic text message (no image)
curl -s -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp%3A%2B919876543210&To=whatsapp%3A%2B14155238886&Body=Hello&NumMedia=0&MessageSid=SM_test_001"

# Message with image (MediaUrl0 is a Twilio media URL)
curl -s -X POST http://localhost:8000/webhook/whatsapp \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=whatsapp%3A%2B919876543210&To=whatsapp%3A%2B14155238886&Body=&NumMedia=1&MediaUrl0=https%3A%2F%2Fapi.twilio.com%2Fmedia%2Ftest.jpg&MediaContentType0=image%2Fjpeg&MessageSid=SM_test_002"
```

### 8c. Write a row directly to translation_logs (verify DB end-to-end)

```bash
# Start a Python shell with the venv and backend app in path
cd /path/to/SehatSamjho
source .venv/bin/activate
cd backend
python3 - <<'EOF'
import asyncio
from app.db.database import AsyncSessionLocal
from app.db.models import TranslationLog

async def insert_test_row():
    async with AsyncSessionLocal() as session:
        row = TranslationLog(
            request_id  = "SM_manual_test_001",
            phone_hash  = "a" * 64,           # fake SHA-256
            language_code = "hi",
            doc_type    = "prescription",
            latency_ms  = 1500,
            drug_count  = 2,
            has_audio   = True,
            status      = "success",
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        print(f"Inserted row id={row.id}  created_at={row.created_at}")
        await session.commit()

asyncio.run(insert_test_row())
EOF
# Expected: Inserted row id=1  created_at=2026-02-27 ...
```

### 8d. Query the database directly

```bash
# Connect to PostgreSQL inside Docker
docker exec -it sehatsamjho-postgres-1 psql -U sehat -d sehatsamjho

# Inside psql:
SELECT id, request_id, language_code, doc_type, latency_ms, status, created_at
FROM translation_logs
ORDER BY created_at DESC
LIMIT 10;

# Count rows by language
SELECT language_code, COUNT(*) FROM translation_logs GROUP BY language_code;

# Check that no PHI is stored (these columns should NOT exist)
\d translation_logs
# You should see: id, created_at, request_id, phone_hash, language_code,
#                 doc_type, latency_ms, drug_count, has_audio, status, error_code
# No: patient_name, phone_number, image_url, prescription_text, diagnosis

\q
```

### 8e. Verify phone hashing works correctly

```bash
cd /path/to/SehatSamjho && source .venv/bin/activate && cd backend
python3 - <<'EOF'
from app.core.security import hash_phone

phone = "whatsapp:+919876543210"
h = hash_phone(phone)
print(f"Input : {phone}")
print(f"Hash  : {h}")
print(f"Length: {len(h)} chars (should be 64)")

# Same input always produces same hash
assert hash_phone(phone) == hash_phone(phone), "Not deterministic!"
# Different inputs produce different hashes
assert hash_phone("whatsapp:+919876543210") != hash_phone("whatsapp:+919876543211")
print("All assertions passed")
EOF
```

### 8f. Run the full test suite and read the output

```bash
source .venv/bin/activate
python -m pytest backend/tests/ -v --tb=short 2>&1 | tee /tmp/test_results.txt

# What each test group validates:
#
# test_database.py  (7 tests)
#   ✓ engine can connect to sehatsamjho database
#   ✓ AsyncSessionLocal returns a working AsyncSession
#   ✓ expire_on_commit=False is set (objects stay alive after commit)
#   ✓ get_db() yields AsyncSession
#   ✓ get_db() commits on clean exit
#   ✓ get_db() rolls back on exception
#
# test_models.py  (9 tests)
#   ✓ table name is "translation_logs"
#   ✓ all 11 columns exist
#   ✓ primary key is "id"
#   ✓ request_id has unique constraint
#   ✓ nullable constraints match the schema
#   ✓ insert + SELECT round-trip in live DB
#   ✓ created_at set automatically by server_default
#   ✓ error_code defaults to NULL
#   ✓ duplicate request_id raises IntegrityError
#
# test_schemas.py  (18 tests)
#   ✓ ConversationState / DocumentType enums have correct values
#   ✓ TwilioWebhookPayload parses Twilio field aliases (From, To, Body...)
#   ✓ extra fields in Twilio payload are silently ignored
#   ✓ missing required fields raise ValidationError
#   ✓ Medication and PrescriptionData defaults are correct
#   ✓ UserSession JSON round-trip preserves all fields
#   ✓ TranslationLogCreate / TranslationLogRead ORM compat
#
# test_security.py  (8 tests)
#   ✓ hash_phone returns 64-char hex string
#   ✓ hash_phone is deterministic and unique per input
#   ✓ hash_phone includes the whatsapp: prefix in the hash
#   ✓ verify_twilio_signature returns True when validation disabled
#   ✓ verify_twilio_signature returns False for bad signature
#   ✓ verify_twilio_signature returns True for correctly signed request
#
# test_main.py  (6 tests)
#   ✓ GET /health returns 200
#   ✓ /health response has {"status": "ok", "env": "..."}
#   ✓ env field matches settings.environment
#   ✓ /docs accessible in debug mode
#   ✓ app.title == "SehatSamjho API"
#   ✓ app.version == "0.1.0"
```

---

## 9. Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `connection refused :5435` | PostgreSQL not running | `make services` |
| `relation "translation_logs" does not exist` | Migration not applied | `make local-migrate` |
| `ValidationError: openai_api_key` | `.env` file missing or incomplete | `cp .env.example .env` then fill required fields |
| `Future attached to a different loop` | asyncpg cross-loop reuse | Already fixed in `conftest.py` — `db_session` is a sync fixture |
| `module 'app.api.webhooks' has no attribute 'router'` | Stub file is empty | Add `from fastapi import APIRouter; router = APIRouter()` to the stub |
| `alembic.util.exc.CommandError: Can't locate revision` | Versions directory has no migrations | Run `alembic revision --autogenerate -m "init"` first |

---

## 10. Key Design Decisions

**Why `db_session` is a sync fixture (not `async def`)**

pytest-asyncio 0.24 runs async fixture teardown on a function-scoped event loop,
but the test body runs on the session-scoped loop. asyncpg connections are bound to
the loop they were opened on — using them from a different loop raises a RuntimeError.
Making `db_session` sync and using `event_loop.run_until_complete(session.close())`
guarantees the close runs on the correct loop.

**Why `event_loop` is session-scoped (deprecated but necessary)**

pytest-asyncio 0.24 gives each test function its own loop by default. With asyncpg,
a pooled connection from test N cannot be reused in test N+1 (different loop).
A session-scoped loop forces all tests onto one loop, preventing cross-loop reuse.
This produces one deprecation warning per run — expected until pytest-asyncio 0.25+.

**Why `datetime.now(timezone.utc)` instead of `datetime.utcnow()`**

`datetime.utcnow()` was deprecated in Python 3.12 (used in the Dockerfile).
`datetime.now(timezone.utc)` returns a timezone-aware datetime, which is also
consistent with the database-side `DateTime(timezone=True)` column type.

**Why `get_db()` commits on clean exit and rolls back on exception**

Each HTTP request gets its own session. If the route handler raises any exception,
the rollback ensures no partial data is written to the DB. The commit on clean exit
means route handlers never need to call `session.commit()` manually.
