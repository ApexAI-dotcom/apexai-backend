#!/bin/bash

echo "🔧 Fix Apex AI - Lovable App"
echo "============================"
echo ""

# Aller dans le dossier lovable-app
cd "$(dirname "$0")"

echo "📦 Étape 1: Installation des dépendances manquantes..."
npm install class-variance-authority clsx tailwind-merge tailwindcss-animate

echo ""
echo "🧹 Étape 2: Nettoyage du cache Vite..."
rm -rf node_modules/.vite

echo ""
echo "✅ Configuration terminée !"
echo ""
echo "🚀 Lancez maintenant : npm run dev"
echo "   L'application sera sur http://localhost:3000"
