#!/bin/bash
set -e

echo "=== DEPLOY ApexAI ==="

# 1. Push backend → Railway
echo "[1/2] Push backend → Railway..."
git add -A
git commit -m "${1:-deploy: backend update}" 2>/dev/null || echo "Rien à commiter côté backend"
git push origin master
echo "✅ Backend poussé"

# 2. Push frontend → Vercel
echo "[2/2] Push frontend → Vercel..."
cd ../apex-ai-fresh
git add -A
git commit -m "${1:-deploy: frontend update}" 2>/dev/null || echo "Rien à commiter côté frontend"
git push origin main
cd ../apexai-backend
echo "✅ Frontend poussé"

echo ""
echo "=== DONE ==="
echo "Railway déploie automatiquement depuis master"
echo "Vercel déploie automatiquement depuis main"
