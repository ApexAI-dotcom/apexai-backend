@echo off
echo 🚨 FIX URGENT - Tailwind v4 PostCSS Error
echo ==========================================
echo.

echo 📦 Étape 1: Désinstallation des anciennes dépendances PostCSS...
call npm uninstall postcss autoprefixer tailwindcss

echo.
echo 📦 Étape 2: Installation du plugin Vite officiel Tailwind v4...
call npm install -D @tailwindcss/vite@latest

echo.
echo 🧹 Étape 3: Nettoyage du cache Vite...
if exist node_modules\.vite rmdir /s /q node_modules\.vite

echo.
echo ✅ Configuration terminée !
echo.
echo 🚀 Lancez maintenant : npm run dev
echo    L'application sera sur http://localhost:3000
pause
