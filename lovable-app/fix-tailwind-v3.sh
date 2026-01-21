#!/bin/bash

echo "🚨 FIX URGENT - Downgrade Tailwind v3 + Fix Shadcn"
echo "=================================================="
echo ""

# Aller dans le dossier lovable-app
cd "$(dirname "$0")"

echo "📦 Étape 1: Désinstallation de Tailwind v4..."
npm uninstall @tailwindcss/vite

echo ""
echo "📦 Étape 2: Installation de Tailwind v3 + PostCSS..."
npm install -D tailwindcss@^3.4.0 postcss autoprefixer

echo ""
echo "🔧 Étape 3: Initialisation Tailwind (vérification)..."
npx tailwindcss init -p --yes || echo "Fichiers déjà créés, continuons..."

echo ""
echo "🧹 Étape 4: Nettoyage du cache Vite..."
rm -rf node_modules/.vite

echo ""
echo "✅ Configuration terminée !"
echo ""
echo "🚀 Lancez maintenant : npm run dev"
echo "   L'application sera sur http://localhost:3000"
