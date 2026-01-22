# Apex AI Backend - Dockerfile (Python 3.11, pas de Poetry)
# Usage: docker build -t apexai-backend . && docker run -p 8000:8000 apexai-backend

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dépendances système légères (matplotlib, scipy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Requirements (pip uniquement, pas Poetry)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Code source
COPY src ./src

# Dossiers runtime
RUN mkdir -p /app/output /app/temp

EXPOSE 8000

# Port Render = $PORT (défaut 8000)
CMD ["sh", "-c", "python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
