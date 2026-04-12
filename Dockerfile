# syntax=docker/dockerfile:1
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    RG_CITIES_DATA_PATH=/tmp/rg_cities1000.csv

# Optional: curl for HEALTHCHECK
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# Copy app
COPY fmdx_statistics ./fmdx_statistics

COPY templates ./templates
COPY static ./static
COPY data ./data

# Run as non-root
RUN useradd -u 10001 -m appuser
USER appuser

EXPOSE 9090

# Healthcheck uses a lightweight route without upstream dependencies
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -fsS http://127.0.0.1:9090/healthz || exit 1

# Gunicorn with Flask app factory
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:9090", "fmdx_statistics.app:create_app()"]
