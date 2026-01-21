@echo off
echo 🚨 FIX URGENT - Downgrade Tailwind v3 + Fix Shadcn
echo ==================================================
echo.

echo 📦 Étape 1: Désinstallation de Tailwind v4...
call npm uninstall @tailwindcss/vite

echo.
echo 📦 Étape 2: Installation de Tailwind v3 + PostCSS...
call npm install -D tailwindcss@^3.4.0 postcss autoprefixer

echo.
echo 🔧 Étape 3: Initialisation Tailwind (vérification)...
call npx tailwindcss init -p --yes 2>nul || echo Fichiers déjà créés, continuons...

echo.
echo 🧹 Étape 4: Nettoyage du cache Vite...
if exist node_modules\.vite rmdir /s /q node_modules\.vite

echo.
echo ✅ Configuration terminée !
echo.
echo 🚀 Lancez maintenant : npm run dev
echo    L'application sera sur http://localhost:3000
pause
