# Checklist — Spec S12.5: Upstash Redis Setup

## Phase 1: Account Setup
- [x] Sign up / log in to Upstash Console (https://console.upstash.com)
- [x] Verify free tier is available for your account

## Phase 2: Create Database
- [x] Click "Create Database"
- [x] Name: `sehatsamjho-prod`
- [x] Region: `ap-south-1` (AWS Mumbai)
- [x] Type: Regional (not Global — free tier)
- [x] TLS: Enabled (default)
- [x] Eviction: Disabled (we want persistent cache)
- [x] Confirm and create

## Phase 3: Record Credentials
- [x] Copy the `rediss://` connection URL from the database details page
- [x] Verify URL starts with `rediss://` (TLS), not `redis://`
- [x] SSH into EC2 and add to `.env`: `REDIS_URL=rediss://default:{password}@{endpoint}:{port}`
- [x] Confirm `.env` is in `.gitignore` — never commit credentials

## Phase 4: Verify Connectivity
- [x] From EC2: Install redis-cli if not present (`sudo apt install redis-tools`)
- [x] Run: `redis-cli -u $REDIS_URL PING` — expect `PONG`
- [x] Run: `redis-cli -u $REDIS_URL SET test:key "hello"` — expect `OK`
- [x] Run: `redis-cli -u $REDIS_URL GET test:key` — expect `"hello"`
- [x] Run: `redis-cli -u $REDIS_URL DEL test:key` — cleanup

## Phase 5: Application Integration
- [x] Update `docker-compose.prod.yml` — ensure no local Redis service (app uses Upstash via REDIS_URL)
- [x] Restart app: `docker compose -f docker-compose.prod.yml up -d`
- [x] Check logs: `docker compose logs app | grep -i redis` — no connection errors
- [x] Verify init_redis ping succeeds in startup logs

## Phase 6: Verification
- [x] Upstash dashboard shows database in Active state
- [x] Region confirmed as ap-south-1
- [x] Connection uses TLS (rediss://)
- [x] PING works from EC2
- [x] App starts without Redis errors
- [x] Usage counter in Upstash dashboard reflects test commands
- [x] All 5 tangible outcomes verified

## Artifacts Created
- `scripts/setup-upstash-redis.sh` — validation script (TLS check, PING, SET/GET, security audit)
- `.env.example` — updated with `rediss://` production format hint
- `docker-compose.prod.yml` — confirmed no local Redis service (app uses external Upstash)
