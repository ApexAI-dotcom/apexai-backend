# Dockerfile à la racine pour Railway (monorepo).
# Le backend réel est dans apexai-backend/ ; ce fichier copie depuis ce dossier.
FROM python:3.11-slim

WORKDIR /app

COPY apexai-backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY apexai-backend/src/ ./src/
COPY apexai-backend/run_api.py .

RUN mkdir -p /app/output /app/temp

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
