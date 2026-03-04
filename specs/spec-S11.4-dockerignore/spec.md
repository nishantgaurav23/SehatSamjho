# Spec S11.4 — Docker Ignore Rules

## Overview
Define a `.dockerignore` file at the repository root to exclude unnecessary files and directories from the Docker build context. This reduces image build time, decreases image size, and prevents sensitive files (like `.env`) from being copied into Docker images. The exclusion list targets virtual environments, cached bytecode, large data files, documentation, version control metadata, and secret files.

## Dependencies
None (standalone configuration file).

## Target Location
`.dockerignore` (repository root)

---

## Functional Requirements

### FR-1: Exclude Python virtual environment
- **What**: The `.venv` directory must be excluded from Docker build context
- **Inputs**: N/A (static file)
- **Outputs**: `.venv` directory not copied during `docker build`
- **Edge cases**: Nested `.venv` paths should also be excluded

### FR-2: Exclude environment secrets
- **What**: `.env` files must never enter the Docker build context to prevent secrets leaking into images
- **Inputs**: N/A
- **Outputs**: `.env`, `.env.*` files excluded
- **Edge cases**: `.env.example` should also be excluded (it's a template, not needed at runtime)

### FR-3: Exclude Python bytecode caches
- **What**: All `__pycache__` directories and `*.pyc` files must be excluded
- **Inputs**: N/A
- **Outputs**: No bytecode artifacts in the build context
- **Edge cases**: Deeply nested `__pycache__` dirs (e.g., `backend/app/services/__pycache__`)

### FR-4: Exclude version control metadata
- **What**: The `.git` directory must be excluded to avoid bloating the build context
- **Inputs**: N/A
- **Outputs**: `.git` not copied
- **Edge cases**: `.gitignore` itself is harmless but unnecessary — exclude or leave (low impact)

### FR-5: Exclude documentation and non-runtime directories
- **What**: `notebooks/`, `docs/`, `specs/` directories are not needed at runtime and should be excluded
- **Inputs**: N/A
- **Outputs**: These directories not in build context
- **Edge cases**: N/A

### FR-6: Exclude large data files selectively
- **What**: Large CSV data files (`data/*.csv`) should be excluded from the build context. Glossary JSON files (`data/glossary/*.json`) ARE needed for seeding and must NOT be excluded
- **Inputs**: N/A
- **Outputs**: `data/drugs/medicines.csv` excluded; `data/glossary/` included
- **Edge cases**: Future CSV files in `data/` should also be excluded by pattern

### FR-7: Exclude test and development artifacts
- **What**: Test directories, IDE configs, and other dev artifacts should be excluded from production images
- **Inputs**: N/A
- **Outputs**: `backend/tests/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `*.egg-info/` excluded
- **Edge cases**: N/A

### FR-8: Exclude Docker-specific files
- **What**: `Dockerfile`, `docker-compose*.yml`, and `.dockerignore` itself are not needed inside the image
- **Inputs**: N/A
- **Outputs**: Docker config files excluded from context
- **Edge cases**: N/A

---

## Tangible Outcomes

- [ ] **Outcome 1**: `.dockerignore` file exists at repository root
- [ ] **Outcome 2**: `.venv` directory is listed in `.dockerignore`
- [ ] **Outcome 3**: `.env` and `.env.*` patterns are listed in `.dockerignore`
- [ ] **Outcome 4**: `**/__pycache__` and `*.pyc` patterns are listed
- [ ] **Outcome 5**: `.git` directory is listed
- [ ] **Outcome 6**: `notebooks/`, `docs/`, `specs/` directories are listed
- [ ] **Outcome 7**: `data/drugs/` (or `data/*.csv`) is excluded but `data/glossary/` is NOT excluded
- [ ] **Outcome 8**: Test/dev artifacts (`backend/tests/`, `.pytest_cache/`, `.ruff_cache/`) are listed
- [ ] **Outcome 9**: Docker config files (`Dockerfile`, `docker-compose*.yml`) are listed
- [ ] **Outcome 10**: File uses valid `.dockerignore` syntax (one pattern per line, `#` comments)

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
1. **test_dockerignore_exists**: Verify `.dockerignore` file exists at repo root
2. **test_dockerignore_not_empty**: File has content (not blank)
3. **test_excludes_venv**: `.venv` pattern present
4. **test_excludes_env_files**: `.env` pattern present
5. **test_excludes_pycache**: `__pycache__` pattern present
6. **test_excludes_pyc**: `*.pyc` pattern present
7. **test_excludes_git**: `.git` pattern present
8. **test_excludes_notebooks**: `notebooks/` or `notebooks` pattern present
9. **test_excludes_docs**: `docs/` or `docs` pattern present
10. **test_excludes_specs**: `specs/` or `specs` pattern present
11. **test_excludes_drug_csv_data**: Pattern excluding drug CSV data files present
12. **test_does_not_exclude_glossary**: `data/glossary/` is NOT in the exclusion list (or is explicitly included via `!` override)
13. **test_excludes_tests**: `backend/tests/` or test directory pattern present
14. **test_excludes_pytest_cache**: `.pytest_cache` pattern present
15. **test_excludes_ruff_cache**: `.ruff_cache` pattern present
16. **test_excludes_dockerfile**: `Dockerfile` pattern present
17. **test_excludes_docker_compose**: `docker-compose*.yml` pattern present
18. **test_valid_syntax**: Every non-empty, non-comment line is a valid pattern (no trailing spaces that could cause issues)
19. **test_has_comments**: File includes descriptive comment sections for organization
20. **test_no_duplicate_patterns**: No exact duplicate lines in the file

### Mocking Strategy
- No mocking needed — this is a static file validation test (like S1.1, S1.2)

### Coverage Expectation
- All patterns verified by at least one test
- Edge case: glossary data explicitly NOT excluded

---

## References
- roadmap.md (Phase 11 — Infra & Seeding)
- Docker documentation: https://docs.docker.com/build/concepts/context/#dockerignore-files
- S11.1 (Dockerfile) — build context uses repo root
