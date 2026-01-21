@echo off
REM 🚀 Script de migration rapide Lovable → Cursor pour ApexAI (Windows)

echo 🚀 Migration Lovable → Cursor - ApexAI
echo ======================================
echo.

set LOVABLE_TEMP_DIR=lovable-temp
set APEXAI_DIR=lovable-app

REM Vérifier que nous sommes dans le bon dossier
if not exist "%APEXAI_DIR%" (
    echo ❌ Erreur: Dossier %APEXAI_DIR% non trouvé
    echo    Exécutez ce script depuis la racine du projet ApexAI
    pause
    exit /b 1
)

REM Étape 1 : Import manuel
echo 📥 Étape 1: Import manuel requis
echo    Placez les fichiers Lovable dans le dossier: %LOVABLE_TEMP_DIR%
pause

REM Vérifier que le dossier existe
if not exist "%LOVABLE_TEMP_DIR%" (
    echo ❌ Erreur: Dossier %LOVABLE_TEMP_DIR% non trouvé
    pause
    exit /b 1
)

REM Étape 2 : Copier les pages
echo.
echo 📄 Étape 2: Copie des pages Lovable...
if exist "%LOVABLE_TEMP_DIR%\src\pages" (
    xcopy /Y /I "%LOVABLE_TEMP_DIR%\src\pages\*.tsx" "%APEXAI_DIR%\src\pages\" 2>nul
    echo ✅ Pages copiées
) else if exist "%LOVABLE_TEMP_DIR%\src\app" (
    echo ✅ Structure Next.js détectée
    echo    Copiez manuellement les fichiers depuis src\app vers src\pages
) else (
    echo ⚠️  Aucune page trouvée dans Lovable
)

REM Étape 3 : Copier les composants
echo.
echo 🧩 Étape 3: Copie des composants Lovable...
if exist "%LOVABLE_TEMP_DIR%\src\components" (
    xcopy /E /Y /I "%LOVABLE_TEMP_DIR%\src\components" "%APEXAI_DIR%\src\components\" 2>nul
    echo ✅ Composants copiés
) else (
    echo ⚠️  Aucun composant trouvé dans Lovable
)

REM Étape 4 : Installer les dépendances
echo.
echo 📦 Étape 4: Installation des dépendances...
cd %APEXAI_DIR%
call npm install
cd ..

REM Étape 5 : Vérification
echo.
echo 🔍 Étape 5: Vérification...
cd %APEXAI_DIR%
call npm run build 2>nul
if errorlevel 1 (
    echo ⚠️  Erreurs détectées. Vérifiez manuellement.
) else (
    echo ✅ Build réussi
)
cd ..

REM Étape 6 : Nettoyage
echo.
set /p CLEANUP="Supprimer le dossier temporaire %LOVABLE_TEMP_DIR% ? (y/n) "
if /i "%CLEANUP%"=="y" (
    rmdir /s /q "%LOVABLE_TEMP_DIR%" 2>nul
    echo ✅ Dossier temporaire supprimé
) else (
    echo ℹ️  Dossier temporaire conservé: %LOVABLE_TEMP_DIR%
)

echo.
echo ✅ Migration terminée !
echo.
echo 📝 Prochaines étapes:
echo    1. Vérifier App.tsx et ajouter les nouvelles routes
echo    2. Tester l'application: cd %APEXAI_DIR% ^&^& npm run dev
echo    3. Vérifier le design purple sur toutes les pages
echo    4. Tester l'intégration avec le backend
echo.
pause
