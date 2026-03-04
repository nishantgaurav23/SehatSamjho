# Spec S11.2 — Docker Compose Dev

## Overview
Local development stack using Docker Compose. Defines three services — PostgreSQL 15, Redis 7, and the application (built from the Dockerfile dev stage). Provides a single `docker compose up --build` command (via `make dev`) to spin up the full local environment. Environment variables loaded from `.env` file.

## Dependencies
- S11.1 (Multi-stage Dockerfile) — must be implemented and passing

## Target Location
- `docker-compose.yml` (project root)

---

## Functional Requirements

### FR-1: Compose file version and structure
- **What**: Valid `docker-compose.yml` at project root using Compose Specification (no `version:` key needed for modern docker compose)
- **Inputs**: N/A (static file)
- **Outputs**: Parseable YAML defining three services: `postgres`, `redis`, `app`
- **Edge cases**: File must be valid YAML; service names must be lowercase

### FR-2: PostgreSQL service (`postgres`)
- **What**: PostgreSQL 15 container for local development
- **Image**: `postgres:15`
- **Environment**: `POSTGRES_USER=postgres`, `POSTGRES_PASSWORD=postgres`, `POSTGRES_DB=sehatsamjho`
- **Ports**: `5432:5432` (host:container)
- **Volumes**: Named volume `postgres_data` mounted to `/var/lib/postgresql/data` for persistence across restarts
- **Healthcheck**: `pg_isready -U postgres` to signal readiness before app starts

### FR-3: Redis service (`redis`)
- **What**: Redis 7 container for sessions, drug cache, and glossary cache
- **Image**: `redis:7`
- **Ports**: `6379:6379` (host:container)
- **Healthcheck**: `redis-cli ping` to signal readiness before app starts

### FR-4: Application service (`app`)
- **What**: FastAPI application built from Dockerfile dev stage
- **Build context**: `.` (project root, matching Dockerfile convention)
- **Build target**: `dev` stage (includes pytest + ruff)
- **Ports**: `8000:8000` (host:container)
- **Environment**: Loaded via `env_file: .env`
- **Override env**: `DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/sehatsamjho` and `REDIS_URL=redis://redis:6379/0` (use Docker service names as hostnames, not localhost)
- **Depends on**: `postgres` (condition: service_healthy), `redis` (condition: service_healthy)
- **Command**: Override CMD to `uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload`
- **Volumes**: Bind mount `./backend:/app/backend` and `./data:/app/data` for hot-reload during development

### FR-5: Named volumes
- **What**: Declare `postgres_data` as a named volume at top level
- **Purpose**: Persist PostgreSQL data across `docker compose down` / `up` cycles (data survives unless `docker compose down -v` is used)

### FR-6: Makefile integration
- **What**: Existing Makefile targets (`dev`, `test`, `migrate`, `seed`) must work with this compose file
- **Verification**: `make dev` runs `docker compose up --build`, `make test` runs pytest inside app container, `make migrate` runs alembic inside app container

---

## Tangible Outcomes

- [ ] **Outcome 1**: `docker-compose.yml` exists at project root and is valid YAML
- [ ] **Outcome 2**: File defines exactly three services: `postgres`, `redis`, `app`
- [ ] **Outcome 3**: PostgreSQL uses `postgres:15` image with correct env vars and named volume
- [ ] **Outcome 4**: Redis uses `redis:7` image with healthcheck
- [ ] **Outcome 5**: App service builds from Dockerfile `dev` target with bind mounts for hot-reload
- [ ] **Outcome 6**: App service overrides DATABASE_URL and REDIS_URL to use Docker service hostnames
- [ ] **Outcome 7**: App depends on postgres and redis with healthcheck conditions
- [ ] **Outcome 8**: Named volume `postgres_data` declared at top level
- [ ] **Outcome 9**: Existing Makefile Docker targets (`dev`, `test`, `migrate`, `seed`) are compatible

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_compose_file_exists**: `docker-compose.yml` exists at project root
2. **test_compose_valid_yaml**: File parses as valid YAML
3. **test_compose_has_services**: Top-level `services` key with exactly 3 entries
4. **test_postgres_service_image**: postgres service uses `postgres:15`
5. **test_postgres_service_environment**: postgres service sets POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
6. **test_postgres_service_ports**: postgres service maps port 5432
7. **test_postgres_service_volume**: postgres service mounts `postgres_data` to `/var/lib/postgresql/data`
8. **test_postgres_service_healthcheck**: postgres service has `pg_isready` healthcheck
9. **test_redis_service_image**: redis service uses `redis:7`
10. **test_redis_service_ports**: redis service maps port 6379
11. **test_redis_service_healthcheck**: redis service has `redis-cli ping` healthcheck
12. **test_app_service_build_context**: app service build context is `.`
13. **test_app_service_build_target**: app service build target is `dev`
14. **test_app_service_ports**: app service maps port 8000
15. **test_app_service_env_file**: app service uses `env_file: .env`
16. **test_app_service_database_url_override**: app environment overrides DATABASE_URL with docker hostname
17. **test_app_service_redis_url_override**: app environment overrides REDIS_URL with docker hostname
18. **test_app_service_depends_on_postgres**: app depends_on postgres with condition service_healthy
19. **test_app_service_depends_on_redis**: app depends_on redis with condition service_healthy
20. **test_app_service_command**: app command includes uvicorn with --reload
21. **test_app_service_bind_mount_backend**: app volumes include `./backend:/app/backend`
22. **test_app_service_bind_mount_data**: app volumes include `./data:/app/data`
23. **test_named_volume_postgres_data**: top-level `volumes` declares `postgres_data`
24. **test_makefile_dev_target_compatible**: Makefile `dev` target uses `docker compose up --build`

### Mocking Strategy
- No mocking needed — all tests are static file validation (YAML parsing + assertion)
- Tests read `docker-compose.yml` from disk and validate structure

### Coverage Expectation
- All services, ports, volumes, healthchecks, and build configuration validated
- ~20-24 tests covering all FRs

---

## References
- roadmap.md (Phase 11, S11.2)
- S11.1 spec (Dockerfile stages: base, dev, prod)
- Docker Compose Specification: https://docs.docker.com/compose/compose-file/
