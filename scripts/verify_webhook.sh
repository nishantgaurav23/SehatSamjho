#!/bin/bash
set -euo pipefail

# ── Verify Twilio Webhook Connectivity ────────────────────────────────────────
# Usage: verify_webhook.sh <EC2_ELASTIC_IP>
# Tests that the deployed SehatSamjho app is reachable and the webhook
# endpoint is live with HMAC signature validation enabled.

EC2_IP="${1:?Usage: verify_webhook.sh <EC2_ELASTIC_IP>}"

echo "=== SehatSamjho Webhook Verification ==="
echo ""

# 1. Health check
echo "1. Health check..."
if curl -sf "http://${EC2_IP}:8000/health" > /dev/null 2>&1; then
    echo "   Health endpoint: OK"
else
    echo "   Health endpoint: FAILED — is the app running on ${EC2_IP}:8000?"
    exit 1
fi

# 2. Webhook endpoint (expect 403 — no valid Twilio signature)
echo "2. Webhook endpoint (expect 403 for unsigned request)..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST \
    "http://${EC2_IP}:8000/webhook/whatsapp" \
    -d "Body=test&From=whatsapp:+0000000000" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "403" ]; then
    echo "   Got 403 (HMAC rejected) — webhook is live and validating signatures. OK"
elif [ "$HTTP_CODE" = "000" ]; then
    echo "   Connection failed — check security group allows inbound on port 8000."
    exit 1
else
    echo "   Got HTTP $HTTP_CODE — unexpected response. Check server logs."
    exit 1
fi

echo ""
echo "=== All checks passed ==="
