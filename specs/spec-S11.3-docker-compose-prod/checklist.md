# Checklist — Spec S11.3: Docker Compose Prod

## Phase 1: Setup & Dependencies
- [x] Verify S11.1 (Dockerfile) is implemented and tests pass
- [x] Confirm `backend/Dockerfile` has `prod` stage
- [x] Locate `docker-compose.yml` (dev) for reference

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s11_3_docker_compose_prod.py`
- [x] Write 20 failing tests for all FRs (static YAML validation)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Create `docker-compose.prod.yml` at project root
- [x] Define single `app` service with build target `prod`
- [x] Configure `env_file: .env` for environment variable passthrough
- [x] Set port mapping `8000:8000`
- [x] Set restart policy `unless-stopped`
- [x] No postgres/redis services, no volumes, no --reload
- [x] Run tests — expect pass (Green)

## Phase 4: Integration
- [x] Verify YAML syntax with `docker compose -f docker-compose.prod.yml config`
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 8 tangible outcomes checked
- [x] No hardcoded secrets or connection strings
- [x] File matches roadmap description
- [x] Update roadmap.md status: spec-written -> done
