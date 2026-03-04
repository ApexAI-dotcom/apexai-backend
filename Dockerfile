# Dockerfile à la racine pour Railway (monorepo).
# Le backend réel est dans apexai-backend/ ; on copie tout le dossier en une fois.
FROM python:3.11-slim

WORKDIR /app

# Copie tout le backend (évite "run_api.py not found" si structure/context diffère)
COPY apexai-backend/ ./
RUN pip install --upgrade pip && pip install -r requirements.txt

RUN mkdir -p /app/output /app/temp

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
