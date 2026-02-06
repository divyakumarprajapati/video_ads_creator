###############################################################################
# Video Ads Engine – multi-stage Dockerfile
###############################################################################

# ── Stage 1: Python base ───────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

# ── Stage 2: API server ───────────────────────────────────
FROM base AS api

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

# ── Stage 3: Celery worker ────────────────────────────────
FROM base AS worker

CMD ["celery", "-A", "app.workers.celery_app", "worker", \
     "--loglevel=info", "--concurrency=2", \
     "-Q", "video_gen,orchestrator"]
