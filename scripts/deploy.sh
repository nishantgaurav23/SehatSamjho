#!/bin/bash
set -euo pipefail

# ── SehatSamjho — EC2 Deployment Script ──────────────────────────────────────
# Run this script on the EC2 instance after creating .env with prod secrets.
# Usage: bash scripts/deploy.sh

cd /home/ubuntu/SehatSamjho

echo "==> Pulling latest code..."
git pull origin feature/sehatsamjo-nishant

echo "==> Building and starting containers..."
docker compose -f docker-compose.prod.yml up -d --build

echo "==> Waiting for app container to be ready..."
sleep 5

echo "==> Running database migrations..."
docker compose -f docker-compose.prod.yml exec app alembic upgrade head

echo "==> Seeding drug + glossary data into Redis..."
docker compose -f docker-compose.prod.yml exec app python backend/scripts/seed.py

echo "==> Deployment complete. Running health check..."
curl -s http://127.0.0.1:8000/health
echo ""
echo "==> Done!"
