.PHONY: dev up down logs build test migrate seed lint shell ngrok build-push clean \
        install install-dev local-dev local-test local-lint local-migrate venv

# ── uv / Local Dev (no Docker) ───────────────────────────────────
# Use these for fast iteration without spinning up containers.
# Requires: PostgreSQL + Redis running locally (or via `make up`).

venv:
	uv venv .venv --python 3.11
	@echo "Activate with: source .venv/bin/activate"

install:
	uv pip install -r pyproject.toml

install-dev:
	uv pip install -r pyproject.toml
	uv pip install pytest==8.3.3 pytest-asyncio==0.24.0 pytest-mock==3.14.0 ruff==0.6.9

local-dev:
	cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

local-test:
	cd backend && ../.venv/bin/pytest tests/ -v --tb=short

local-lint:
	.venv/bin/ruff check backend/app/ scripts/
	.venv/bin/ruff format --check backend/app/ scripts/

local-migrate:
	cd backend && ../.venv/bin/alembic upgrade head

# ── Docker: Local Development ─────────────────────────────────────
dev:
	docker-compose up --build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f api

build:
	docker-compose build

shell:
	docker-compose run --rm api python

# ── Database ─────────────────────────────────────────────────────
migrate:
	docker-compose run --rm api alembic upgrade head

migrate-down:
	docker-compose run --rm api alembic downgrade -1

makemigrations:
	docker-compose run --rm api alembic revision --autogenerate -m "$(msg)"

# ── Data ─────────────────────────────────────────────────────────
seed:
	docker-compose run --rm api python scripts/seed_drug_db.py
	docker-compose run --rm api python scripts/seed_glossary.py

fetch-drugs:
	docker-compose run --rm api python scripts/fetch_drug_data.py

# ── Code Quality ─────────────────────────────────────────────────
lint:
	docker-compose run --rm api ruff check app/ scripts/
	docker-compose run --rm api ruff format --check app/ scripts/

format:
	docker-compose run --rm api ruff format app/ scripts/

test:
	docker-compose run --rm api pytest tests/ -v --tb=short

test-cov:
	docker-compose run --rm api pytest tests/ -v --cov=app --cov-report=term-missing

# ── Tunnel (Twilio webhook dev) ───────────────────────────────────
ngrok:
	ngrok http 8000

# ── AWS Deployment ────────────────────────────────────────────────
ECR_REGISTRY ?= $(AWS_ACCOUNT_ID).dkr.ecr.ap-south-1.amazonaws.com
IMAGE_NAME    ?= sehatsamjho/api
IMAGE_TAG     ?= $(shell git rev-parse --short HEAD)

build-image:
	docker build -f backend/Dockerfile -t $(IMAGE_NAME):$(IMAGE_TAG) .
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(ECR_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(ECR_REGISTRY)/$(IMAGE_NAME):latest

ecr-login:
	aws ecr get-login-password --region ap-south-1 | \
		docker login --username AWS --password-stdin $(ECR_REGISTRY)

push:
	docker push $(ECR_REGISTRY)/$(IMAGE_NAME):$(IMAGE_TAG)
	docker push $(ECR_REGISTRY)/$(IMAGE_NAME):latest

build-push: build-image push

deploy-staging:
	aws ecs update-service \
		--cluster sehatsamjho-cluster \
		--service sehatsamjho-api-staging \
		--force-new-deployment \
		--region ap-south-1

deploy-prod:
	@echo "⚠️  Deploying to PRODUCTION. Ctrl+C to cancel."
	@sleep 3
	aws ecs update-service \
		--cluster sehatsamjho-cluster \
		--service sehatsamjho-api-prod \
		--force-new-deployment \
		--region ap-south-1

# ── Cleanup ───────────────────────────────────────────────────────
clean:
	docker-compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true
	find . -type f -name ".coverage" -delete 2>/dev/null; true

# ── Setup (first time) ────────────────────────────────────────────
setup:
	cp -n .env.example .env || true
	docker-compose pull
	docker-compose build
	$(MAKE) migrate
	$(MAKE) seed
	@echo ""
	@echo "Setup complete! Run 'make dev' to start."
	@echo "Then run 'make ngrok' in another terminal to get your Twilio webhook URL."
