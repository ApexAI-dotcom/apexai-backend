#!/bin/bash

echo "🚨 FIX URGENT - Tailwind v4 PostCSS Error"
echo "=========================================="
echo ""

# Aller dans le dossier lovable-app
cd "$(dirname "$0")"

echo "📦 Étape 1: Désinstallation des anciennes dépendances PostCSS..."
npm uninstall postcss autoprefixer tailwindcss

echo ""
echo "📦 Étape 2: Installation du plugin Vite officiel Tailwind v4..."
npm install -D @tailwindcss/vite@latest

echo ""
echo "🧹 Étape 3: Nettoyage du cache Vite..."
rm -rf node_modules/.vite

echo ""
echo "✅ Configuration terminée !"
echo ""
echo "🚀 Lancez maintenant : npm run dev"
echo "   L'application sera sur http://localhost:3000"
