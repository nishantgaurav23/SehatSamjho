# Spec S12.5 — Upstash Redis Setup

## Overview
Provision a free-tier Upstash Redis database in the ap-south-1 (Mumbai) region to serve as the production Redis instance. Upstash provides a serverless Redis with a generous free tier (256MB storage, 10K requests/day) — sufficient for the SehatSamjho prototype's session management, drug cache, and glossary cache. The connection URL is stored in the production `.env` as `REDIS_URL`.

## Dependencies
- None (standalone cloud service provisioning)

## Target Location
Upstash Console / docs (no code files — infrastructure configuration)

---

## Functional Requirements

### FR-1: Create Upstash Account and Database
- **What**: Sign up for Upstash (if not already) and create a new Redis database
- **Database name**: `sehatsamjho-prod`
- **Region**: `ap-south-1` (AWS Mumbai) — same region as EC2 for lowest latency
- **Plan**: Free tier (256MB, 10K commands/day)
- **Edge cases**: If ap-south-1 unavailable, use closest available region (ap-southeast-1)

### FR-2: Enable TLS and Password Authentication
- **What**: Upstash databases have TLS enabled by default. Verify the connection string uses `rediss://` (TLS) not `redis://`
- **Authentication**: Upstash provides a password in the connection URL — no additional configuration needed
- **Edge cases**: Ensure the application's `redis.asyncio` client supports TLS (`rediss://` scheme)

### FR-3: Record Connection URL as REDIS_URL
- **What**: Copy the full connection string from the Upstash dashboard
- **Format**: `rediss://default:{password}@{endpoint}:{port}`
- **Store in**: Production `.env` file on EC2 as `REDIS_URL=rediss://...`
- **Edge cases**: Never commit the connection string to git — `.env` is in `.gitignore`

### FR-4: Verify Connectivity from EC2
- **What**: From the EC2 instance, confirm the application can connect to Upstash Redis
- **Test**: Run `redis-cli -u $REDIS_URL PING` — should return `PONG`
- **Application test**: Start the app container and verify Redis health check passes on startup (init_redis ping)

### FR-5: Verify Free Tier Limits Are Sufficient
- **What**: Confirm the 10K req/day and 256MB storage limits cover prototype usage
- **Session commands**: ~10 per conversation (get/set/delete) × estimated 50 conversations/day = 500 commands
- **Drug cache**: ~1000 entries × ~200 bytes = ~200KB
- **Glossary cache**: ~600 entries × ~300 bytes = ~180KB
- **Total storage**: <1MB (well within 256MB)
- **Edge cases**: If approaching limits, Upstash shows usage in dashboard — monitor during testing

---

## Tangible Outcomes

- [ ] **Outcome 1**: Upstash Redis database `sehatsamjho-prod` exists in ap-south-1 region
- [ ] **Outcome 2**: Connection URL uses `rediss://` (TLS enabled)
- [ ] **Outcome 3**: `REDIS_URL` is set in production `.env` on EC2 (not committed to git)
- [ ] **Outcome 4**: `redis-cli -u $REDIS_URL PING` returns `PONG` from EC2
- [ ] **Outcome 5**: Application startup (init_redis) succeeds against Upstash — no connection errors in logs

---

## Test-Driven Requirements

### Manual Verification Steps (No Automated Tests — Cloud Console / CLI)
1. **verify_database_exists**: Upstash dashboard shows `sehatsamjho-prod` database in Active state
2. **verify_region**: Database details page shows region as `ap-south-1` (or closest alternative)
3. **verify_tls**: Connection string starts with `rediss://`
4. **verify_ping_from_ec2**: SSH to EC2 → `redis-cli -u $REDIS_URL PING` → `PONG`
5. **verify_set_get**: SSH to EC2 → `redis-cli -u $REDIS_URL SET test:key "hello"` then `GET test:key` → `"hello"`
6. **verify_app_startup**: `docker compose -f docker-compose.prod.yml up -d` → no Redis connection errors in `docker compose logs app`
7. **verify_env_not_in_git**: `git grep REDIS_URL` shows only `.env.example` (placeholder), not actual credentials
8. **verify_usage_dashboard**: Upstash dashboard shows command count increasing after app interactions

### Mocking Strategy
- N/A — this is an infrastructure spec with manual verification

### Coverage Expectation
- All 8 verification steps pass on the live environment

---

## References
- roadmap.md (Phase 12, S12.5)
- Upstash Redis documentation: https://docs.upstash.com/redis
- backend/app/db/redis.py (init_redis uses REDIS_URL from settings)
- backend/app/core/config.py (REDIS_URL field)
