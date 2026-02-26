FROM python:3.12-slim AS base

WORKDIR /app

# Install uv for fast, reproducible dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# System deps: ffmpeg (pydub audio), gcc + libpq-dev (asyncpg compilation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml first — Docker layer cache means deps only rebuild
# when pyproject.toml changes, not on every code change
COPY pyproject.toml .
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy application code from backend/
COPY backend/ .

# ── Development target (default) ─────────────────────────────────
FROM base AS development
# Install dev deps for make test / make lint inside container
RUN uv pip install --system --no-cache \
    pytest==8.3.3 pytest-asyncio==0.24.0 pytest-mock==3.14.0 ruff==0.6.9
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production target ─────────────────────────────────────────────
FROM base AS production
# Non-root user for security — never run as root in prod
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

EXPOSE 8000
