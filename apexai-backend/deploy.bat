@echo off
setlocal

echo === DEPLOY ApexAI ===

echo [1/2] Push backend → Railway...
git add -A
git commit -m "%~1" 2>nul || echo Rien a commiter cote backend
git push origin master
echo Backend poussé ✓

echo [2/2] Push frontend → Vercel...
cd ..\apex-ai-fresh
git add -A
git commit -m "%~1" 2>nul || echo Rien a commiter cote frontend
git push origin main
cd ..\apexai-backend
echo Frontend poussé ✓

echo.
echo === DONE ===
