#!/bin/bash

# 🚀 Script de migration rapide Lovable → Cursor pour ApexAI

set -e

echo "🚀 Migration Lovable → Cursor - ApexAI"
echo "======================================"
echo ""

# Variables
LOVABLE_REPO_URL="${1:-}"
LOVABLE_TEMP_DIR="lovable-temp"
APEXAI_DIR="lovable-app"

# Vérifier que nous sommes dans le bon dossier
if [ ! -d "$APEXAI_DIR" ]; then
    echo "❌ Erreur: Dossier $APEXAI_DIR non trouvé"
    echo "   Exécutez ce script depuis la racine du projet ApexAI"
    exit 1
fi

# Étape 1 : Cloner/Importer Lovable
if [ -n "$LOVABLE_REPO_URL" ]; then
    echo "📥 Étape 1: Clonage du repo Lovable..."
    if [ -d "$LOVABLE_TEMP_DIR" ]; then
        echo "⚠️  Dossier $LOVABLE_TEMP_DIR existe déjà. Suppression..."
        rm -rf "$LOVABLE_TEMP_DIR"
    fi
    git clone "$LOVABLE_REPO_URL" "$LOVABLE_TEMP_DIR"
else
    echo "📥 Étape 1: Import manuel requis"
    echo "   Placez les fichiers Lovable dans le dossier: $LOVABLE_TEMP_DIR"
    read -p "   Appuyez sur Entrée une fois les fichiers copiés..."
fi

# Vérifier que le dossier existe
if [ ! -d "$LOVABLE_TEMP_DIR" ]; then
    echo "❌ Erreur: Dossier $LOVABLE_TEMP_DIR non trouvé"
    exit 1
fi

# Étape 2 : Copier les pages
echo ""
echo "📄 Étape 2: Copie des pages Lovable..."
if [ -d "$LOVABLE_TEMP_DIR/src/pages" ]; then
    cp -n "$LOVABLE_TEMP_DIR/src/pages"/*.tsx "$APEXAI_DIR/src/pages/" 2>/dev/null || true
    echo "✅ Pages copiées"
elif [ -d "$LOVABLE_TEMP_DIR/src/app" ]; then
    # Structure Next.js
    find "$LOVABLE_TEMP_DIR/src/app" -name "*.tsx" -exec cp -n {} "$APEXAI_DIR/src/pages/" \; 2>/dev/null || true
    echo "✅ Pages copiées (structure Next.js)"
else
    echo "⚠️  Aucune page trouvée dans Lovable"
fi

# Étape 3 : Copier les composants
echo ""
echo "🧩 Étape 3: Copie des composants Lovable..."
if [ -d "$LOVABLE_TEMP_DIR/src/components" ]; then
    # Copier sans écraser les composants existants
    find "$LOVABLE_TEMP_DIR/src/components" -type f \( -name "*.tsx" -o -name "*.ts" \) -exec sh -c '
        dest="$APEXAI_DIR/src/components/$(basename "$(dirname "$1")")/$(basename "$1")"
        mkdir -p "$(dirname "$dest")"
        if [ ! -f "$dest" ]; then
            cp "$1" "$dest"
        fi
    ' _ {} \;
    echo "✅ Composants copiés"
else
    echo "⚠️  Aucun composant trouvé dans Lovable"
fi

# Étape 4 : Corriger les imports
echo ""
echo "🔧 Étape 4: Correction des imports..."
find "$APEXAI_DIR/src" -type f \( -name "*.tsx" -o -name "*.ts" \) -exec sed -i.bak \
    -e 's|from "\.\./\.\./components|from "@/components|g' \
    -e 's|from "\.\./components|from "@/components|g' \
    -e 's|from "\.\./\.\./lib|from "@/lib|g' \
    -e 's|from "\.\./lib|from "@/lib|g' \
    -e 's|from "\.\./\.\./pages|from "@/pages|g' \
    -e 's|from "\.\./pages|from "@/pages|g' \
    {} \;

# Supprimer les fichiers de backup
find "$APEXAI_DIR/src" -name "*.bak" -delete

echo "✅ Imports corrigés"

# Étape 5 : Installer les dépendances
echo ""
echo "📦 Étape 5: Installation des dépendances..."
cd "$APEXAI_DIR"
npm install
cd ..

# Étape 6 : Vérification TypeScript
echo ""
echo "🔍 Étape 6: Vérification TypeScript..."
cd "$APEXAI_DIR"
if npm run build 2>&1 | grep -q "error"; then
    echo "⚠️  Erreurs TypeScript détectées. Vérifiez manuellement."
else
    echo "✅ Pas d'erreurs TypeScript majeures"
fi
cd ..

# Étape 7 : Nettoyage
echo ""
echo "🧹 Étape 7: Nettoyage..."
read -p "Supprimer le dossier temporaire $LOVABLE_TEMP_DIR ? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$LOVABLE_TEMP_DIR"
    echo "✅ Dossier temporaire supprimé"
else
    echo "ℹ️  Dossier temporaire conservé: $LOVABLE_TEMP_DIR"
fi

echo ""
echo "✅ Migration terminée !"
echo ""
echo "📝 Prochaines étapes:"
echo "   1. Vérifier App.tsx et ajouter les nouvelles routes"
echo "   2. Tester l'application: cd $APEXAI_DIR && npm run dev"
echo "   3. Vérifier le design purple sur toutes les pages"
echo "   4. Tester l'intégration avec le backend"
