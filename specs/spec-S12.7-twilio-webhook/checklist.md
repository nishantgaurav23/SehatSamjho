# Checklist — Spec S12.7: Twilio Webhook URL Update

## Phase 1: Setup & Dependencies
- [x] Verify S12.6 (Deploy to EC2) is implemented — app running, health check passing
- [x] Verify S1.5 (Twilio HMAC) is implemented — signature validation in webhook
- [x] Confirm EC2 security group allows inbound on port 8000
- [x] Confirm `TWILIO_AUTH_TOKEN` in EC2 `.env` matches Twilio Console

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s12_7_twilio_webhook.py`
- [x] Write 21 failing tests for verify script and configuration validation
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Create `scripts/verify_webhook.sh` with shebang + safety flags
- [x] Add EC2 IP argument parsing with usage message
- [x] Add health check curl command
- [x] Add webhook POST test (expect 403 for unsigned request)
- [x] Add result echo messages
- [x] Make script executable (`chmod +x`)
- [x] Run tests — expect pass (Green)

## Phase 4: Integration
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 21 tests passing
- [x] No hardcoded secrets or IPs in scripts
- [x] Verify script uses correct port and paths

## Phase 6: Manual Configuration (Twilio Console)
- [ ] Log in to Twilio Console
- [ ] Navigate to WhatsApp Sandbox settings
- [ ] Set webhook URL: `http://{EC2_IP}:8000/webhook/whatsapp`
- [ ] Set method: POST
- [ ] Save configuration
- [ ] Send test WhatsApp message to Sandbox number
- [ ] Verify bot responds with welcome message
- [ ] Check EC2 Docker logs for successful processing
- [ ] Run `bash scripts/verify_webhook.sh {EC2_IP}` to confirm
- [ ] Update roadmap.md status: pending -> done (when verified)
