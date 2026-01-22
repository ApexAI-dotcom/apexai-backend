@echo off
echo 🚀 Démarrage Backend APEX AI
echo ============================
cd backend
echo.
echo Installation des dependances...
pip install -r requirements.txt
echo.
echo Démarrage du serveur FastAPI...
python main.py
pause
