# ===========================================================================
# Stage 1: base — Python 3.11 + uv + production dependencies
# ===========================================================================
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy dependency manifest first (layer caching: deps rebuild only when pyproject.toml changes)
COPY pyproject.toml /app/pyproject.toml

# Install production dependencies into system Python (no venv inside Docker)
RUN uv pip install --system -r pyproject.toml

# ===========================================================================
# Stage 2: dev — base + test/lint tools
# ===========================================================================
FROM base AS dev

# Install dev extras (pytest, ruff, pytest-asyncio, pytest-mock, httpx)
RUN uv pip install --system -r pyproject.toml --extra dev

# Copy application source and data
COPY backend/ /app/backend/
COPY data/ /app/data/

CMD ["pytest"]

# ===========================================================================
# Stage 3: prod — production image with non-root user
# ===========================================================================
FROM base AS prod

# Copy application source and data
COPY backend/ /app/backend/
COPY data/ /app/data/

# Create non-root user and set ownership
RUN useradd --create-home appuser && chown -R appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
