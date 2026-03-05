# Checklist — Spec S12.6: Deploy to EC2

## Phase 1: Setup & Dependencies
- [x] Verify S12.1 (EC2 setup) is implemented — instance running, Docker installed
- [x] Verify S12.2 (RDS setup) is implemented — database endpoint available
- [x] Verify S12.3 (S3 bucket) is implemented — bucket created
- [x] Verify S12.4 (IAM role) is implemented — instance profile attached
- [x] Verify S12.5 (Upstash Redis) is implemented — Redis URL available
- [x] Verify S11.3 (Docker Compose Prod) is implemented — `docker-compose.prod.yml` ready
- [x] Verify `.gitignore` includes `.env` and `*.pem`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s12_6_deploy_ec2.py`
- [x] Write 24 tests for deploy script and security practices (exceeded 20 target)
- [x] Run `make local-test` — expect failures (Red) — 17 failed, 7 passed

## Phase 3: Implementation
- [x] Create `scripts/deploy.sh` with shebang + safety flags
- [x] Add git pull command to deploy script
- [x] Add docker compose up --build -d command
- [x] Add alembic migration command
- [x] Add seed script command
- [x] Add health check verification
- [x] Add completion echo message
- [x] Make deploy script executable (`chmod +x`)
- [x] Update `.gitignore` with `.env` and `*.pem` entries if missing — already present
- [x] Run tests — expect pass (Green) — 24/24 passed

## Phase 4: Integration
- [x] Run `make local-lint` — passed (ruff check + format)
- [x] Run full test suite: `make local-test` — 1405/1405 passed

## Phase 5: Verification
- [x] All 24 tests passing
- [x] No hardcoded secrets in deploy script
- [x] `.gitignore` excludes sensitive files
- [x] Deploy script uses prod compose file specifically
- [x] Update roadmap.md status: spec-written -> done

## Phase 6: Manual Deployment (on EC2)
- [ ] SSH to EC2 instance
- [ ] Clone repository
- [ ] Create `.env` with prod secrets (permissions 600)
- [ ] Run `bash scripts/deploy.sh`
- [ ] Verify health check: `curl http://<ELASTIC_IP>:8000/health`
- [ ] Check Docker logs for connectivity errors
- [ ] Confirm `interaction_log` table exists in RDS
- [ ] Confirm drug + glossary data in Upstash Redis
