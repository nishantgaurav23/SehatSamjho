# Spec S12.7 — Twilio Webhook URL Update

## Overview
Configure the Twilio WhatsApp Sandbox (or production number) to point its webhook URL at the deployed EC2 instance. Set the incoming message webhook to `http://{EC2_ELASTIC_IP}:8000/webhook/whatsapp` with method POST. Verify end-to-end connectivity by sending a test WhatsApp message and confirming HMAC signature validation (S1.5) works correctly on the live server.

## Dependencies
- S12.6 (Deploy to EC2) — application running and healthy on EC2
- S1.5 (Twilio HMAC verification) — signature validation implemented in webhook endpoint

## Target Location
- Twilio Console: WhatsApp Sandbox / Messaging Service webhook configuration
- Verification script: `scripts/verify_webhook.sh` (optional helper)

---

## Functional Requirements

### FR-1: Configure Twilio Webhook URL
- **What**: Set the WhatsApp Sandbox (or production) webhook URL in Twilio Console
- **Inputs**: EC2 Elastic IP, Twilio Console access
- **Outputs**: Webhook URL set to `http://{EC2_ELASTIC_IP}:8000/webhook/whatsapp`, method POST
- **Steps**:
  1. Log in to Twilio Console
  2. Navigate to Messaging > Try it out > Send a WhatsApp message (Sandbox) or Messaging Services (production)
  3. Set "When a message comes in" URL to `http://{EC2_ELASTIC_IP}:8000/webhook/whatsapp`
  4. Set HTTP method to POST
  5. Save configuration
- **Edge cases**: URL must use port 8000 (not 80/443) unless reverse proxy configured, Twilio requires publicly reachable URL

### FR-2: Verify HMAC Signature Validation
- **What**: Confirm that Twilio's HMAC signature is correctly validated by the deployed webhook
- **Inputs**: WhatsApp test message sent to Twilio Sandbox number
- **Outputs**: Server accepts valid Twilio requests (200), rejects forged requests (403)
- **Verification**:
  1. Send a WhatsApp message to the Sandbox number (e.g., "join <sandbox-keyword>")
  2. Check EC2 Docker logs for successful webhook processing (no 403 errors)
  3. Optionally send a curl request without valid signature — expect 403
- **Edge cases**: `TWILIO_AUTH_TOKEN` in `.env` must match the Twilio Console auth token exactly

### FR-3: Verify End-to-End Message Flow
- **What**: Confirm the full conversation flow works via WhatsApp
- **Inputs**: WhatsApp message from test phone
- **Outputs**: Bot responds with welcome message + language selection
- **Steps**:
  1. Send any message to the Twilio WhatsApp Sandbox number
  2. Expect: welcome/consent message followed by language selection buttons
  3. Select a language (e.g., "1" for Hindi)
  4. Expect: "Please send a photo of your prescription" prompt
- **Edge cases**: First message after Sandbox join may be the join confirmation, not the bot response

### FR-4: Verify Webhook Script (Optional Helper)
- **What**: Create a `scripts/verify_webhook.sh` script that tests webhook connectivity
- **Inputs**: EC2 Elastic IP (passed as argument or read from environment)
- **Outputs**: Script checks health endpoint and simulates a basic webhook test
- **Contents**:
  ```bash
  #!/bin/bash
  set -euo pipefail
  EC2_IP="${1:?Usage: verify_webhook.sh <EC2_ELASTIC_IP>}"
  echo "1. Health check..."
  curl -sf "http://${EC2_IP}:8000/health" && echo " OK" || echo " FAILED"
  echo "2. Webhook endpoint exists (expect 403 — no valid Twilio signature)..."
  HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" -X POST "http://${EC2_IP}:8000/webhook/whatsapp" -d "Body=test" 2>/dev/null || true)
  if [ "$HTTP_CODE" = "403" ]; then
    echo "   Got 403 (HMAC rejected) — webhook is live and validating signatures. OK"
  else
    echo "   Got $HTTP_CODE — unexpected response. Check server logs."
  fi
  ```

### FR-5: Security Group Verification
- **What**: Ensure EC2 security group allows inbound traffic on port 8000 from Twilio's IP ranges
- **Inputs**: EC2 security group configuration
- **Outputs**: Port 8000 open for inbound HTTP from 0.0.0.0/0 (Twilio uses many IPs)
- **Edge cases**: If only port 80/443 is open, need either a reverse proxy (nginx) or to change security group to also allow 8000

### FR-6: Docker Logs Monitoring
- **What**: Verify webhook requests appear in application logs
- **Inputs**: Docker compose logs on EC2
- **Outputs**: Log entries showing incoming webhook requests with request_id
- **Commands**:
  ```bash
  docker compose -f docker-compose.prod.yml logs --tail=100 -f app
  ```
- **Edge cases**: Loguru output format may differ in Docker (ensure structured logging works)

---

## Tangible Outcomes

- [ ] **Outcome 1**: Twilio Console webhook URL set to `http://{EC2_IP}:8000/webhook/whatsapp` (POST)
- [ ] **Outcome 2**: WhatsApp test message triggers welcome response from bot
- [ ] **Outcome 3**: HMAC validation accepts valid Twilio requests (no 403 in logs)
- [ ] **Outcome 4**: Unsigned/forged requests to webhook return 403
- [ ] **Outcome 5**: `scripts/verify_webhook.sh` exists and is executable
- [ ] **Outcome 6**: Docker logs show incoming webhook requests with request_id
- [ ] **Outcome 7**: Security group allows inbound on port 8000

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

Since S12.7 is a deployment/configuration spec, tests validate the verify script and configuration artifacts:

1. **test_verify_script_exists**: `scripts/verify_webhook.sh` exists
2. **test_verify_script_executable**: Script has executable permission
3. **test_verify_script_has_shebang**: Script starts with `#!/bin/bash`
4. **test_verify_script_has_set_euo**: Script uses `set -euo pipefail`
5. **test_verify_script_accepts_ip_arg**: Script references `$1` or positional argument for EC2 IP
6. **test_verify_script_checks_health**: Script curls the `/health` endpoint
7. **test_verify_script_checks_webhook**: Script sends POST to `/webhook/whatsapp`
8. **test_verify_script_expects_403**: Script checks for 403 response (HMAC rejection)
9. **test_verify_script_no_hardcoded_secrets**: Script contains no API keys or tokens
10. **test_verify_script_no_hardcoded_ips**: Script does not hardcode Elastic IPs
11. **test_verify_script_uses_port_8000**: Script references port 8000
12. **test_webhook_endpoint_path_correct**: `backend/app/api/webhooks.py` has route `/webhook/whatsapp`
13. **test_webhook_method_is_post**: Webhook route accepts POST method
14. **test_security_module_imported**: `webhooks.py` imports or references security/HMAC validation
15. **test_twilio_auth_token_in_env_example**: `.env.example` contains `TWILIO_AUTH_TOKEN`
16. **test_twilio_whatsapp_from_in_env_example**: `.env.example` contains `TWILIO_WHATSAPP_FROM`
17. **test_deploy_script_exists**: `scripts/deploy.sh` exists (dependency from S12.6)
18. **test_docker_compose_prod_exposes_port**: `docker-compose.prod.yml` exposes port 8000
19. **test_verify_script_prints_results**: Script contains `echo` for user feedback
20. **test_verify_script_usage_message**: Script shows usage if no argument provided

### Mocking Strategy
- No external service mocking needed — tests are static file validation

### Coverage Expectation
- All script contents validated statically
- Webhook endpoint configuration verified via code inspection
- Security practices confirmed (no hardcoded secrets)

---

## References
- roadmap.md — Phase 12: AWS Deployment
- specs/spec-S12.6-deploy-ec2/ — EC2 deployment (prerequisite)
- specs/spec-S1.5-twilio-hmac/ — HMAC signature validation
- specs/spec-S4.1-webhook-endpoint/ — Webhook endpoint implementation
- Twilio WhatsApp Sandbox docs: https://www.twilio.com/docs/whatsapp/sandbox
