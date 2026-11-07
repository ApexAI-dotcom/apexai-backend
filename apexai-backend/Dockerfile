FROM python:3.11-slim

# Calcul numérique sur un seul fil : le conteneur voit tous les cœurs de la
# machine hôte mais n'en a que quelques-uns ; OpenBLAS lançait un fil par cœur
# visible et se marchait dessus (Tour Parfait IA : 13 s en production contre
# 1 s en local). Une analyse à la fois (file d'attente), un fil chacune.
ENV OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src/ ./src/
COPY run_api.py .

# Créer les dossiers requis par l'application
RUN mkdir -p /app/output /app/temp

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
