# 🔄 Étapes détaillées de migration Lovable → Cursor

## 📥 Étape 1 : Préparation

### 1.1 Sauvegarder le projet actuel

```bash
# Créer une branche de sauvegarde
cd ApexAI
git checkout -b backup-before-lovable-migration
git add .
git commit -m "Backup before Lovable migration"
```

### 1.2 Créer un dossier temporaire pour Lovable

```bash
# À la racine du projet
mkdir lovable-temp
cd lovable-temp
```

## 📥 Étape 2 : Importer le code Lovable

### Option A : Depuis GitHub

```bash
# Cloner le repo Lovable
git clone https://github.com/votre-username/votre-repo-lovable.git .
```

### Option B : Depuis ZIP téléchargé

```bash
# Extraire le ZIP
unzip lovable-project.zip
# OU sur Windows
# Extraire manuellement avec 7-Zip ou WinRAR
```

### Option C : Copier depuis Lovable.dev

1. **Exporter** le projet depuis Lovable.dev
2. **Télécharger** le ZIP
3. **Extraire** dans `lovable-temp/`

## 🔍 Étape 3 : Analyser la structure Lovable

### 3.1 Examiner les fichiers

```bash
# Voir la structure
tree lovable-temp/src
# OU
find lovable-temp/src -type f -name "*.tsx" -o -name "*.ts"
```

### 3.2 Identifier les pages

```bash
# Lister les pages
ls lovable-temp/src/pages/
# OU
ls lovable-temp/src/app/  # Si structure Next.js
```

### 3.3 Identifier les composants

```bash
# Lister les composants
ls lovable-temp/src/components/
```

## 🔀 Étape 4 : Fusion avec ApexAI

### 4.1 Copier les pages (avec vérification)

```bash
# Depuis la racine ApexAI
cd lovable-app/src/pages

# Copier les nouvelles pages Lovable
cp ../../../lovable-temp/src/pages/*.tsx . 2>/dev/null || true
cp ../../../lovable-temp/src/app/**/*.tsx . 2>/dev/null || true

# Vérifier les conflits
ls -la
```

### 4.2 Copier les composants (avec merge)

```bash
cd ../components

# Copier les nouveaux composants (sans écraser)
cp -n ../../../lovable-temp/src/components/**/* . 2>/dev/null || true
```

### 4.3 Mettre à jour les assets

```bash
# Copier les images/assets si nécessaire
cp -r ../../../lovable-temp/src/assets/* src/assets/ 2>/dev/null || true
```

## 🔧 Étape 5 : Corrections automatiques

### 5.1 Script de correction des imports

Créer `fix-imports.sh` :

```bash
#!/bin/bash
# Fix imports in all TSX/TS files

find lovable-app/src -name "*.tsx" -o -name "*.ts" | while read file; do
  # Remplacer les imports relatifs par @/
  sed -i 's|from "\.\./\.\./components|from "@/components|g' "$file"
  sed -i 's|from "\.\./components|from "@/components|g' "$file"
  sed -i 's|from "\.\./\.\./lib|from "@/lib|g' "$file"
  sed -i 's|from "\.\./lib|from "@/lib|g' "$file"
  sed -i 's|from "\.\./\.\./pages|from "@/pages|g' "$file"
done

echo "✅ Imports corrigés"
```

### 5.2 Exécuter le script

```bash
chmod +x fix-imports.sh
./fix-imports.sh
```

## 📝 Étape 6 : Mise à jour du router

### 6.1 Modifier App.tsx

```typescript
// Ajouter les imports des nouvelles pages Lovable
import NewPage1 from "./pages/NewPage1";
import NewPage2 from "./pages/NewPage2";
// ... autres pages

// Ajouter les routes
<Routes>
  <Route path="/" element={<Index />} />
  <Route path="/upload" element={<UploadPage />} />
  <Route path="/new-page-1" element={<NewPage1 />} />
  <Route path="/new-page-2" element={<NewPage2 />} />
  {/* Autres routes Lovable */}
</Routes>
```

## ✅ Étape 7 : Vérifications

### 7.1 Vérifier TypeScript

```bash
cd lovable-app
npm run build
```

### 7.2 Vérifier les imports

```bash
# Chercher les imports incorrects
grep -r "from '\.\./" src/
grep -r "from \"\.\./" src/
```

### 7.3 Vérifier Tailwind

```bash
# Vérifier que toutes les classes existent
npm run build
```

### 7.4 Tester l'application

```bash
npm run dev
# Ouvrir http://localhost:3000
# Tester toutes les pages
```

## 🐛 Étape 8 : Résolution des erreurs

### Erreurs communes et solutions

#### Erreur : "Cannot find module '@/components'"

**Solution** :
```bash
# Vérifier tsconfig.app.json
cat lovable-app/tsconfig.app.json | grep paths
```

#### Erreur : "Module not found"

**Solution** :
```bash
# Installer les dépendances manquantes
cd lovable-app
npm install
```

#### Erreur : "Tailwind class not found"

**Solution** :
```bash
# Vérifier tailwind.config.js
# Ajouter les chemins manquants dans content: []
```

## 🎨 Étape 9 : Harmonisation du design

### 9.1 Vérifier les couleurs

S'assurer que toutes les pages utilisent le thème purple :

```typescript
// Classes à utiliser
"bg-gradient-to-br from-purple-950 via-slate-900 to-purple-950"
"text-purple-400"
"border-purple-500/20"
"bg-purple-500/10"
```

### 9.2 Vérifier les composants Shadcn

S'assurer que tous les composants utilisent ceux de `@/components/ui/` :

```typescript
// ✅ Correct
import { Button } from "@/components/ui/button"

// ❌ Incorrect
import { Button } from "./components/Button"
```

## 📦 Étape 10 : Finalisation

### 10.1 Nettoyer les fichiers temporaires

```bash
# Supprimer le dossier temporaire
rm -rf lovable-temp
```

### 10.2 Commit des changements

```bash
git add .
git commit -m "feat: Integrate Lovable pages and components"
```

### 10.3 Documentation

Mettre à jour `README.md` avec les nouvelles pages :

```markdown
## Pages disponibles

- `/` - Page d'accueil
- `/upload` - Upload CSV MyChron
- `/new-page-1` - [Description]
- `/new-page-2` - [Description]
```

## ✅ Checklist finale

- [ ] Code Lovable importé
- [ ] Pages copiées et fonctionnelles
- [ ] Composants intégrés
- [ ] Router mis à jour
- [ ] Imports corrigés
- [ ] TypeScript sans erreurs
- [ ] Tailwind compatible
- [ ] Design purple harmonisé
- [ ] Backend API fonctionnelle
- [ ] Tests effectués
- [ ] Documentation mise à jour

---

**Migration complète** 🏎️
