#!/bin/bash
echo "🚀 Démarrage Backend APEX AI"
echo "============================"
cd apexai-backend
echo ""
echo "Installation des dépendances..."
pip install -r requirements.txt
echo ""
echo "Démarrage du serveur FastAPI..."
python run_api.py
