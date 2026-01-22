#!/bin/bash
echo "🚀 Démarrage Backend APEX AI"
echo "============================"
cd backend
echo ""
echo "Installation des dépendances..."
pip install -r requirements.txt
echo ""
echo "Démarrage du serveur FastAPI..."
python main.py
