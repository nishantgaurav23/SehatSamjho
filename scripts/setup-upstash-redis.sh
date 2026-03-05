#!/usr/bin/env bash
# ===========================================================================
# Upstash Redis Setup Guide & Validation — SehatSamjho (S12.5)
#
# This script validates an Upstash Redis connection. The database itself
# must be created manually via the Upstash Console (https://console.upstash.com).
#
# Manual Steps (do these BEFORE running this script):
#   1. Sign up / log in at https://console.upstash.com
#   2. Click "Create Database"
#      - Name: sehatsamjho-prod
#      - Region: ap-south-1 (AWS Mumbai)
#      - Type: Regional (free tier)
#      - TLS: Enabled (default)
#      - Eviction: Disabled
#   3. Copy the rediss:// connection URL from the database details page
#   4. On EC2, add to .env: REDIS_URL=rediss://default:{password}@{endpoint}:{port}
#
# Prerequisites:
#   - redis-cli installed (sudo apt install redis-tools)
#   - REDIS_URL set in environment or .env file
#
# Usage:
#   chmod +x scripts/setup-upstash-redis.sh
#   ./scripts/setup-upstash-redis.sh
# ===========================================================================
set -euo pipefail

# ---- Colors ----
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
ERRORS=0

echo "=============================================="
echo " S12.5 — Upstash Redis Validation"
echo "=============================================="
echo ""

# ---- Load REDIS_URL ----
if [ -z "${REDIS_URL:-}" ]; then
    if [ -f .env ]; then
        REDIS_URL=$(grep -E '^REDIS_URL=' .env | cut -d'=' -f2- | tr -d '"' || true)
    fi
fi

if [ -z "${REDIS_URL:-}" ]; then
    fail "REDIS_URL not set. Set it in .env or export it."
    echo ""
    echo "Expected format: rediss://default:{password}@{endpoint}:{port}"
    exit 1
fi
ok "REDIS_URL is set"

# ---- Check TLS (rediss://) ----
echo ""
echo "── Checking TLS ──"
if [[ "$REDIS_URL" == rediss://* ]]; then
    ok "Connection URL uses rediss:// (TLS enabled)"
else
    fail "Connection URL does NOT use rediss:// — expected TLS. Got: ${REDIS_URL:0:10}..."
fi

# ---- Check redis-cli availability ----
echo ""
echo "── Checking redis-cli ──"
if command -v redis-cli &>/dev/null; then
    ok "redis-cli is installed"
else
    fail "redis-cli not found. Install with: sudo apt install redis-tools"
    echo ""
    echo "Skipping connectivity tests."
    exit 1
fi

# ---- PING test ----
echo ""
echo "── Connectivity Tests ──"
PING_RESULT=$(redis-cli -u "$REDIS_URL" PING 2>&1 || true)
if [ "$PING_RESULT" = "PONG" ]; then
    ok "PING → PONG"
else
    fail "PING failed: $PING_RESULT"
fi

# ---- SET/GET test ----
SET_RESULT=$(redis-cli -u "$REDIS_URL" SET "test:s12.5:key" "hello-sehatsamjho" EX 60 2>&1 || true)
if [ "$SET_RESULT" = "OK" ]; then
    ok "SET test:s12.5:key → OK"
else
    fail "SET failed: $SET_RESULT"
fi

GET_RESULT=$(redis-cli -u "$REDIS_URL" GET "test:s12.5:key" 2>&1 || true)
if [ "$GET_RESULT" = "hello-sehatsamjho" ]; then
    ok "GET test:s12.5:key → hello-sehatsamjho"
else
    fail "GET failed: $GET_RESULT"
fi

# ---- Cleanup ----
redis-cli -u "$REDIS_URL" DEL "test:s12.5:key" &>/dev/null || true
ok "Cleaned up test key"

# ---- Check .env not in git ----
echo ""
echo "── Security Check ──"
GIT_GREP_RESULT=$(git grep -l 'REDIS_URL=rediss://' 2>/dev/null || true)
if [ -z "$GIT_GREP_RESULT" ]; then
    ok "No real REDIS_URL credentials committed to git"
else
    fail "REDIS_URL with credentials found in tracked files: $GIT_GREP_RESULT"
fi

# ---- Summary ----
echo ""
echo "=============================================="
if [ "$ERRORS" -eq 0 ]; then
    echo -e " ${GREEN}All checks passed!${NC} Upstash Redis is ready."
else
    echo -e " ${RED}${ERRORS} check(s) failed.${NC} Review above."
fi
echo "=============================================="
exit "$ERRORS"
