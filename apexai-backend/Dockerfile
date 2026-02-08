# Apex AI Backend - Docker
# Build: docker build -t apexai-backend .
# Run:   docker run -p 8000:8000 apexai-backend

FROM python:3.11-slim

WORKDIR /app

# Dépendances système pour scipy/numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Copier requirements
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY . .

# Créer dossiers temp et output
RUN mkdir -p temp output

ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
