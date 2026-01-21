@echo off
echo 🔧 Fix Apex AI - Lovable App
echo ============================
echo.

echo 📦 Étape 1: Installation des dépendances manquantes...
call npm install class-variance-authority clsx tailwind-merge tailwindcss-animate

echo.
echo 🧹 Étape 2: Nettoyage du cache Vite...
if exist node_modules\.vite rmdir /s /q node_modules\.vite

echo.
echo ✅ Configuration terminée !
echo.
echo 🚀 Lancez maintenant : npm run dev
echo    L'application sera sur http://localhost:3000
pause
