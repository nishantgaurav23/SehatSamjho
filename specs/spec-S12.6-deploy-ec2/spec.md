# Spec S12.6 — Deploy to EC2

## Overview
Deploy the SehatSamjho Docker container to the provisioned EC2 t3.micro instance. SSH into EC2, clone the repository, create the production `.env` file with all secrets (RDS, Upstash Redis, OpenAI, Anthropic, Twilio, Bhashini, S3), start the application with `docker compose -f docker-compose.prod.yml up -d`, run Alembic migrations, and seed drug + glossary data into Redis.

## Dependencies
- S12.1 (EC2 t3.micro setup) — instance running with Docker installed
- S12.2 (RDS db.t3.micro PostgreSQL) — database endpoint available
- S12.3 (S3 bucket setup) — audio bucket created
- S12.4 (IAM role for EC2) — instance profile attached for S3 access
- S12.5 (Upstash Redis setup) — Redis URL available
- S11.3 (Docker Compose Prod) — `docker-compose.prod.yml` ready

## Target Location
- EC2 instance: `/home/ubuntu/SehatSamjho/` (cloned repo)
- EC2 instance: `/home/ubuntu/SehatSamjho/.env` (prod secrets)
- Deployment script: `scripts/deploy.sh` (optional helper)

---

## Functional Requirements

### FR-1: SSH and Clone Repository
- **What**: Connect to EC2 via SSH and clone the SehatSamjho repo
- **Inputs**: EC2 Elastic IP, SSH key (`.pem` file), GitHub repo URL
- **Outputs**: Repo cloned to `/home/ubuntu/SehatSamjho/`
- **Edge cases**: SSH key permissions (must be 400), git not installed (install via apt)

### FR-2: Create Production .env File
- **What**: Create `.env` file on EC2 with all required production secrets
- **Inputs**: All secret values from various service consoles (RDS, Upstash, Twilio, OpenAI, Anthropic, Bhashini, S3)
- **Outputs**: `/home/ubuntu/SehatSamjho/.env` with all 12 environment variables populated
- **Edge cases**: File permissions (600, readable only by owner), no secrets committed to git
- **Required variables**:
  - `DATABASE_URL` — RDS PostgreSQL connection string (`postgresql+asyncpg://ssadmin:<password>@<rds-endpoint>:5432/sehatsamjho`)
  - `REDIS_URL` — Upstash Redis URL (`rediss://default:<token>@<endpoint>:6379`)
  - `OPENAI_API_KEY` — OpenAI API key
  - `ANTHROPIC_API_KEY` — Anthropic API key
  - `TWILIO_ACCOUNT_SID` — Twilio account SID
  - `TWILIO_AUTH_TOKEN` — Twilio auth token
  - `TWILIO_WHATSAPP_FROM` — Twilio WhatsApp sender number (e.g., `whatsapp:+14155238886`)
  - `BHASHINI_API_KEY` — Bhashini API key
  - `BHASHINI_USER_ID` — Bhashini user ID
  - `AWS_ACCESS_KEY_ID` — (empty if using IAM instance profile)
  - `AWS_SECRET_ACCESS_KEY` — (empty if using IAM instance profile)
  - `S3_BUCKET` — S3 bucket name (e.g., `sehatsamjho-audio-{account_id}`)

### FR-3: Start Application with Docker Compose
- **What**: Build and start the application using the production Docker Compose file
- **Inputs**: `docker-compose.prod.yml`, `.env` file
- **Outputs**: Application container running on port 8000, accessible via EC2 Elastic IP
- **Commands**:
  ```bash
  cd /home/ubuntu/SehatSamjho
  docker compose -f docker-compose.prod.yml up -d --build
  ```
- **Edge cases**: Port 8000 already in use, Docker daemon not running, build failures due to network issues

### FR-4: Run Database Migrations
- **What**: Execute Alembic migrations against the RDS PostgreSQL database
- **Inputs**: Running app container with DATABASE_URL configured
- **Outputs**: `interaction_log` table created in RDS
- **Commands**:
  ```bash
  docker compose -f docker-compose.prod.yml exec app alembic upgrade head
  ```
- **Edge cases**: RDS not reachable (security group misconfigured), migration already applied (idempotent — Alembic handles this)

### FR-5: Seed Data into Redis
- **What**: Load drug CSV and glossary JSON files into Upstash Redis
- **Inputs**: Running app container with REDIS_URL configured
- **Outputs**: Drug data and glossary entries loaded into Redis
- **Commands**:
  ```bash
  docker compose -f docker-compose.prod.yml exec app python backend/scripts/seed.py
  ```
- **Edge cases**: Upstash rate limits (10K req/day free tier — seeding uses ~2K requests for 1000 drugs + 600 glossary entries), Redis connection timeout

### FR-6: Verify Deployment
- **What**: Confirm the application is healthy and all services are connected
- **Inputs**: EC2 Elastic IP
- **Outputs**: Health check returns `{"status": "ok"}`
- **Verification steps**:
  1. `curl http://<ELASTIC_IP>:8000/health` — expect `{"status": "ok"}`
  2. Check Docker logs: `docker compose -f docker-compose.prod.yml logs --tail=50 app`
  3. Verify no error logs related to DB/Redis connectivity
- **Edge cases**: Security group not allowing port 8000/80 inbound, application crash on startup

### FR-7: Deploy Script (Optional Helper)
- **What**: Create a `scripts/deploy.sh` convenience script for repeatable deployments
- **Inputs**: None (runs on EC2)
- **Outputs**: Script that pulls latest code, rebuilds, and restarts
- **Contents**:
  ```bash
  #!/bin/bash
  set -euo pipefail
  cd /home/ubuntu/SehatSamjho
  git pull origin feature/sehatsamjo-nishant
  docker compose -f docker-compose.prod.yml up -d --build
  docker compose -f docker-compose.prod.yml exec app alembic upgrade head
  docker compose -f docker-compose.prod.yml exec app python backend/scripts/seed.py
  echo "Deployment complete. Health check:"
  curl -s http://localhost:8000/health
  ```

---

## Tangible Outcomes

- [ ] **Outcome 1**: Repository cloned on EC2 at `/home/ubuntu/SehatSamjho/`
- [ ] **Outcome 2**: `.env` file created with all 12 production variables, file permissions 600
- [ ] **Outcome 3**: `docker compose -f docker-compose.prod.yml up -d` starts the app container successfully
- [ ] **Outcome 4**: `curl http://<ELASTIC_IP>:8000/health` returns `{"status": "ok"}`
- [ ] **Outcome 5**: Alembic migration creates `interaction_log` table in RDS
- [ ] **Outcome 6**: Seed script loads drugs + glossary data into Upstash Redis
- [ ] **Outcome 7**: Docker logs show no connectivity errors for DB, Redis, or external APIs
- [ ] **Outcome 8**: `scripts/deploy.sh` exists and is executable

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)

Since S12.6 is a deployment/infrastructure spec (not application code), tests validate:

1. **test_deploy_script_exists**: `scripts/deploy.sh` exists and is executable
2. **test_deploy_script_has_shebang**: Script starts with `#!/bin/bash`
3. **test_deploy_script_has_set_euo**: Script uses `set -euo pipefail` for safety
4. **test_deploy_script_pulls_code**: Script contains `git pull`
5. **test_deploy_script_docker_compose_up**: Script contains `docker compose -f docker-compose.prod.yml up`
6. **test_deploy_script_runs_migrations**: Script contains `alembic upgrade head`
7. **test_deploy_script_runs_seed**: Script contains `seed.py`
8. **test_deploy_script_health_check**: Script contains health check curl
9. **test_env_example_has_all_prod_vars**: `.env.example` contains all 12 required variables
10. **test_env_not_in_git**: `.env` is in `.gitignore`
11. **test_docker_compose_prod_exists**: `docker-compose.prod.yml` exists (dependency check)
12. **test_docker_compose_prod_uses_env_file**: Prod compose references `.env` or `env_file`
13. **test_deploy_script_no_hardcoded_secrets**: Script contains no API keys or passwords
14. **test_deploy_script_no_hardcoded_ips**: Script does not hardcode Elastic IPs
15. **test_gitignore_excludes_env**: `.gitignore` contains `.env` entry
16. **test_gitignore_excludes_pem**: `.gitignore` contains `*.pem` entry
17. **test_deploy_script_uses_prod_compose**: Script specifically uses `docker-compose.prod.yml` not `docker-compose.yml`
18. **test_deploy_script_builds_fresh**: Script includes `--build` flag
19. **test_deploy_script_detached_mode**: Script includes `-d` flag for detached mode
20. **test_deploy_script_echoes_completion**: Script prints completion/status message

### Mocking Strategy
- No external service mocking needed — tests are static file validation (same pattern as S1.1, S1.2, S11.1, S11.4)

### Coverage Expectation
- All deploy script contents validated statically
- All security practices verified (no secrets, .gitignore rules)

---

## References
- roadmap.md — Phase 12: AWS Deployment
- specs/spec-S12.1-ec2-setup/ — EC2 instance setup
- specs/spec-S12.2-rds-setup/ — RDS database setup
- specs/spec-S12.3-s3-bucket/ — S3 bucket setup
- specs/spec-S12.4-iam-role/ — IAM role setup
- specs/spec-S12.5-upstash-redis/ — Upstash Redis setup
- specs/spec-S11.3-docker-compose-prod/ — Production Docker Compose
