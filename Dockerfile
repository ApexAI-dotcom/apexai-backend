# Apex AI - API Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copier requirements
COPY requirements.txt requirements_api.txt ./

# Installer dépendances Python
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r requirements_api.txt

# Copier le code source
COPY . .

# Créer dossiers nécessaires
RUN mkdir -p temp output data logs

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Exposer le port
EXPOSE 8000

# Commande de démarrage
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
