# Checklist — Spec S11.1: Multi-stage Dockerfile

## Phase 1: Setup & Dependencies
- [x] Verify S1.1 is implemented (pyproject.toml exists with all deps)
- [x] Confirm build context assumption: repo root
- [x] Create target file: `backend/Dockerfile`

## Phase 2: Tests First (TDD)
- [x] Write test file: `backend/tests/test_s11_1_dockerfile.py`
- [x] Write 20 failing tests (static Dockerfile parsing)
- [x] Run `make local-test` — expect failures (Red)

## Phase 3: Implementation
- [x] Implement base stage: python:3.11-slim, uv, pyproject.toml copy, dep install
- [x] Implement dev stage: extend base, install dev extras, copy source + data
- [x] Implement prod stage: extend base, copy source + data, non-root user, EXPOSE, CMD
- [x] Run tests — expect pass (Green)
- [x] Refactor if needed (optimize layer ordering, reduce image size)

## Phase 4: Integration
- [x] Verify Dockerfile builds successfully: `docker build -f backend/Dockerfile --target base .`
- [x] Verify dev target builds: `docker build -f backend/Dockerfile --target dev .`
- [x] Verify prod target builds: `docker build -f backend/Dockerfile --target prod .`
- [x] Run `make local-lint`
- [x] Run full test suite: `make local-test`

## Phase 5: Verification
- [x] All 10 tangible outcomes checked
- [x] No hardcoded secrets in Dockerfile
- [x] Layer caching optimized (pyproject.toml before source)
- [x] Non-root user in prod stage
- [x] Update roadmap.md status: spec-written -> done (when ready)
