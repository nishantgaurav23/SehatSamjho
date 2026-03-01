# SehatSamjho — Developer Commands
# Usage: make <target>

.PHONY: venv install install-dev local-dev local-test local-lint local-migrate seed dev test migrate

# ── Local Development ────────────────────────────────────────────────────────

venv:
	python3.11 -m venv .venv

install:
	uv pip install -r pyproject.toml

install-dev:
	uv pip install -r pyproject.toml --extra dev

local-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

local-test:
	cd backend && python -m pytest tests/ -v --tb=short

local-lint:
	ruff check backend/ && ruff format --check backend/

local-migrate:
	cd backend && alembic upgrade head

# ── Docker ───────────────────────────────────────────────────────────────────

dev:
	docker compose up --build

test:
	docker compose exec app python -m pytest tests/ -v --tb=short

migrate:
	docker compose exec app alembic upgrade head

seed:
	docker compose exec app python -m scripts.seed
