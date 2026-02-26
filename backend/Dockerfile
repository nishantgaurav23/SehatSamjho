FROM python:3.12-slim AS base

WORKDIR /app

# System deps for pydub (ffmpeg) and asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# ── Development target (default) ────────────────────────────────
FROM base AS development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production target ────────────────────────────────────────────
FROM base AS production
# Non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

EXPOSE 8000
