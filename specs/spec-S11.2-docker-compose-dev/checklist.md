# Checklist — Spec S11.2: Docker Compose Dev

## Phase 1: Setup & Dependencies
- [x] Verify S11.1 (Dockerfile) is implemented and tests pass
- [x] Locate target file: `docker-compose.yml` at project root
- [x] No new pyproject.toml dependencies needed (static config file)

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s11_2_docker_compose_dev.py`
- [x] Write failing tests for FR-1 (file exists, valid YAML, 3 services)
- [x] Write failing tests for FR-2 (postgres: image, env, ports, volume, healthcheck)
- [x] Write failing tests for FR-3 (redis: image, ports, healthcheck)
- [x] Write failing tests for FR-4 (app: build context/target, ports, env_file, env overrides, depends_on, command, volumes)
- [x] Write failing tests for FR-5 (named volumes declaration)
- [x] Write failing tests for FR-6 (Makefile compatibility)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Create `docker-compose.yml` at project root
- [x] Implement FR-2 — postgres service (image, env, ports, volume, healthcheck)
- [x] Implement FR-3 — redis service (image, ports, healthcheck)
- [x] Implement FR-4 — app service (build, ports, env_file, env overrides, depends_on, command, volumes)
- [x] Implement FR-5 — named volumes section
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed

## Phase 4: Integration
- [x] Verify Makefile `dev` target works: `make dev` spins up all 3 services
- [x] Verify Makefile `test` target works: `make test` runs pytest in container
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All tangible outcomes checked
- [x] No hardcoded secrets (all via .env)
- [x] DATABASE_URL and REDIS_URL use Docker service hostnames (not localhost)
- [x] Bind mounts enable hot-reload for development
- [x] Update roadmap.md status: spec-written -> done
