# Spec S11.3 — Docker Compose Prod

## Overview
Production Docker Compose override file (`docker-compose.prod.yml`) that targets the prod stage of the multi-stage Dockerfile. Unlike the dev stack (S11.2), the prod compose file does **not** spin up local PostgreSQL or Redis containers — it expects external DATABASE_URL (AWS RDS) and REDIS_URL (Upstash) provided via environment variables. Exposes port 8000 for the FastAPI application.

## Dependencies
- S11.1 (Multi-stage Dockerfile) — prod stage must exist

## Target Location
- `docker-compose.prod.yml` (project root)

---

## Functional Requirements

### FR-1: Production compose file structure
- **What**: A valid `docker-compose.prod.yml` file at the project root with a single `app` service
- **Inputs**: None (static file)
- **Outputs**: Valid YAML that Docker Compose can parse
- **Edge cases**: Must be valid YAML; no syntax errors

### FR-2: App service targets prod stage
- **What**: The `app` service builds from `backend/Dockerfile` with `target: prod` (not dev)
- **Inputs**: Build context is repo root (`.`), dockerfile is `backend/Dockerfile`
- **Outputs**: Docker image built from the prod stage (non-root user, no dev tools)
- **Edge cases**: Must specify `target: prod` explicitly

### FR-3: No local database or Redis services
- **What**: The prod compose file must NOT define `postgres` or `redis` services — these are external (RDS + Upstash)
- **Inputs**: N/A
- **Outputs**: Only the `app` service is defined
- **Edge cases**: No `depends_on` for postgres/redis since they don't exist in this file

### FR-4: Environment variables from host
- **What**: DATABASE_URL and REDIS_URL must come from the host environment (or `.env` file), not hardcoded in the compose file
- **Inputs**: `env_file: .env` or environment variable passthrough
- **Outputs**: App container receives DATABASE_URL pointing to RDS, REDIS_URL pointing to Upstash
- **Edge cases**: Must not hardcode any connection strings; must not override DATABASE_URL/REDIS_URL with local values

### FR-5: Port exposure
- **What**: The app service exposes port 8000 (host:container mapping `8000:8000`)
- **Inputs**: N/A
- **Outputs**: Port 8000 accessible from host
- **Edge cases**: Only port 8000 exposed; no debug ports

### FR-6: Restart policy
- **What**: The app service uses `restart: unless-stopped` for production resilience
- **Inputs**: N/A
- **Outputs**: Container auto-restarts on crash unless manually stopped
- **Edge cases**: N/A

### FR-7: No volume mounts for source code
- **What**: Prod does NOT mount local source code as volumes (code is baked into the image via COPY)
- **Inputs**: N/A
- **Outputs**: No `volumes` section mapping `./backend` or `./data`
- **Edge cases**: Data directory is COPYed in the Dockerfile prod stage, not mounted

### FR-8: No --reload flag
- **What**: The prod service must NOT use `--reload` in the uvicorn command (uses the Dockerfile CMD default)
- **Inputs**: N/A
- **Outputs**: Uvicorn runs without hot-reload
- **Edge cases**: If `command` is specified, it must not include `--reload`

---

## Tangible Outcomes

- [ ] **Outcome 1**: `docker-compose.prod.yml` exists at project root and is valid YAML
- [ ] **Outcome 2**: Only one service (`app`) is defined — no postgres, no redis
- [ ] **Outcome 3**: App service builds with `target: prod` from `backend/Dockerfile`
- [ ] **Outcome 4**: DATABASE_URL and REDIS_URL are not hardcoded — sourced from env_file or environment passthrough
- [ ] **Outcome 5**: Port 8000 is exposed
- [ ] **Outcome 6**: Restart policy is `unless-stopped`
- [ ] **Outcome 7**: No source code volume mounts
- [ ] **Outcome 8**: No `--reload` flag in the command (or no command override, using Dockerfile CMD)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_prod_compose_file_exists**: File exists at `docker-compose.prod.yml`
2. **test_prod_compose_valid_yaml**: File parses as valid YAML
3. **test_prod_compose_has_services_key**: Top-level `services` key exists
4. **test_prod_compose_app_service_exists**: `services.app` is defined
5. **test_prod_compose_no_postgres_service**: No `services.postgres` key
6. **test_prod_compose_no_redis_service**: No `services.redis` key
7. **test_prod_compose_only_app_service**: Only `app` in services (no other services)
8. **test_prod_compose_build_context**: Build context is `.` (repo root)
9. **test_prod_compose_build_dockerfile**: Dockerfile path is `backend/Dockerfile`
10. **test_prod_compose_build_target_prod**: Build target is `prod`
11. **test_prod_compose_port_8000**: Port mapping includes `8000:8000`
12. **test_prod_compose_env_file**: Uses `env_file: .env` (or similar)
13. **test_prod_compose_no_hardcoded_database_url**: No hardcoded DATABASE_URL in environment section
14. **test_prod_compose_no_hardcoded_redis_url**: No hardcoded REDIS_URL in environment section
15. **test_prod_compose_restart_policy**: Restart policy is `unless-stopped`
16. **test_prod_compose_no_source_volumes**: No volume mounts for `./backend` or `./data`
17. **test_prod_compose_no_reload_flag**: No `--reload` in command (or no command key)
18. **test_prod_compose_no_depends_on**: No `depends_on` key (no local services to depend on)
19. **test_prod_compose_no_volumes_section**: No top-level `volumes` key (no named volumes needed)
20. **test_prod_compose_differs_from_dev**: Prod file has different structure from dev compose (target, services, etc.)

### Mocking Strategy
- No mocking needed — all tests are static YAML file validation (pure file reads + assertions)

### Coverage Expectation
- All 8 FRs covered by at least one test; edge cases covered via negative assertions

---

## References
- roadmap.md (S11.3 row)
- S11.1 spec (Dockerfile stages)
- S11.2 spec (docker-compose.yml dev stack for comparison)
- Docker Compose documentation
