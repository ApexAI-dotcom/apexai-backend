# 🚀 Script de Déploiement Rapide ApexAI
# Usage: .\deploy.ps1

Write-Host "🚀 Déploiement ApexAI en Production" -ForegroundColor Cyan
Write-Host ""

# Étape 1: Build Frontend
Write-Host "📦 ÉTAPE 1: Build Frontend..." -ForegroundColor Yellow
Set-Location apex-ai-fresh
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur lors du build" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Build terminé!" -ForegroundColor Green
Write-Host ""

# Étape 2: Déploiement Vercel
Write-Host "🌐 ÉTAPE 2: Déploiement Vercel..." -ForegroundColor Yellow
Write-Host "Connectez-vous à Vercel si demandé..." -ForegroundColor Gray
vercel --prod
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Erreur lors du déploiement Vercel" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Déployé sur Vercel!" -ForegroundColor Green
Write-Host ""

Set-Location ..

Write-Host "✅ Déploiement terminé!" -ForegroundColor Green
Write-Host ""
Write-Host "📋 Prochaines étapes:" -ForegroundColor Cyan
Write-Host "1. Configurer le backend sur Railway.app" -ForegroundColor White
Write-Host "2. Ajouter les variables d'environnement sur Vercel" -ForegroundColor White
Write-Host "3. Configurer le domaine apexai.pro (optionnel)" -ForegroundColor White
Write-Host ""
Write-Host "📖 Guide complet: DEPLOY.md" -ForegroundColor Gray
