# ==============================================================================
# Multi-Stage Dockerfile for Google Photos Discovery Engine
# ==============================================================================

# Stage 1: Build & Dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install virtualenv
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy package configurations and source for dependency resolution
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --upgrade pip setuptools wheel && \
    pip install . && \
    pip install google-play-scraper app-store-scraper requests urllib3 spacy && \
    python -m spacy download en_core_web_sm || true

# Stage 2: Runtime Production Image
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000 \
    DATA_DIR=/app/data

# Create dedicated non-root user for security
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/bash -m appuser

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code and assets
COPY src/ /app/src/
COPY scripts/ /app/scripts/
COPY frontend/ /app/frontend/
COPY data/ /app/data/
COPY pyproject.toml /app/

# Set file ownership to non-root appuser
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Default command: Serve discovery web UI and API
CMD ["python", "scripts/serve_frontend.py", "--no-browser"]
