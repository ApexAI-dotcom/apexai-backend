# 🚀 Guide de Migration Lovable → Cursor - ApexAI

## 📋 Vue d'ensemble

Ce guide vous permet de migrer votre projet Lovable vers Cursor et de l'intégrer avec la structure ApexAI existante.

## 🔄 Étape 1 : Importer le code depuis GitHub

### Option A : Cloner le repo GitHub dans Cursor

1. **Ouvrir Cursor**
2. **File → Open Folder** → Créer un nouveau dossier `lovable-import`
3. **Terminal dans Cursor** :
```bash
cd lovable-import
git clone https://github.com/votre-username/votre-repo-lovable.git .
```

### Option B : Importer directement depuis GitHub

1. **Dans Cursor** : `Ctrl+Shift+P` (ou `Cmd+Shift+P` sur Mac)
2. **Taper** : `Git: Clone`
3. **Coller l'URL GitHub** de votre repo Lovable
4. **Sélectionner** le dossier de destination

### Option C : Copier les fichiers manuellement

1. **Télécharger** le ZIP depuis GitHub
2. **Extraire** dans un dossier temporaire
3. **Copier** les fichiers dans `lovable-app/src/` de votre projet ApexAI

## 🔧 Étape 2 : Structure de migration

### Structure actuelle ApexAI

```
ApexAI/
├── backend/
│   ├── main.py              # FastAPI avec analyse CSV MyChron
│   └── requirements.txt
│
└── lovable-app/
    ├── src/
    │   ├── pages/
    │   │   ├── index.tsx        # Page d'accueil
    │   │   └── UploadPage.tsx   # Page upload CSV
    │   ├── components/
    │   │   ├── ui/              # Shadcn components
    │   │   └── layout/
    │   │       └── Layout.tsx
    │   └── App.tsx
    └── ...
```

### Structure après migration

```
ApexAI/
├── backend/
│   ├── main.py              # FastAPI (existant)
│   └── requirements.txt
│
└── lovable-app/
    ├── src/
    │   ├── pages/
    │   │   ├── index.tsx        # Page accueil (existant)
    │   │   ├── UploadPage.tsx   # Page upload (existant)
    │   │   └── [pages Lovable]  # Nouvelles pages Lovable
    │   ├── components/
    │   │   ├── ui/              # Shadcn (existant)
    │   │   ├── layout/          # Layout (existant)
    │   │   └── [composants Lovable]  # Nouveaux composants Lovable
    │   └── App.tsx              # Router mis à jour
    └── ...
```

## 📝 Étape 3 : Prompt de migration dans Cursor

### Prompt à exécuter dans Cursor Chat

```
This project was built in Lovable.dev and needs to be migrated to Cursor.

PROJECT CONTEXT:
- ApexAI: Karting telemetry analysis system
- Backend: FastAPI (Python) - analyzes MyChron CSV files
- Frontend: React + TypeScript + Tailwind + Shadcn UI
- Design: Purple glassmorphism theme

EXISTING STRUCTURE:
- backend/main.py: FastAPI endpoint /api/upload for CSV analysis
- lovable-app/src/pages/index.tsx: Homepage with hero section
- lovable-app/src/pages/UploadPage.tsx: CSV upload page with purple design
- lovable-app/src/components/ui/: Shadcn components (Button, Card, etc.)
- lovable-app/src/components/layout/Layout.tsx: Layout wrapper

MIGRATION TASKS:
1. Review all Lovable pages and components
2. Integrate Lovable pages into lovable-app/src/pages/
3. Integrate Lovable components into lovable-app/src/components/
4. Update App.tsx router to include all Lovable routes
5. Ensure Shadcn UI components are used (not replaced)
6. Maintain purple glassmorphism design theme
7. Update imports to use @/ aliases
8. Ensure compatibility with existing backend API (/api/upload)
9. Fix any TypeScript errors
10. Ensure Tailwind classes are compatible with existing config

CONSTRAINTS:
- Keep existing UploadPage.tsx and index.tsx
- Maintain purple design theme
- Use existing Shadcn components
- Preserve backend API integration
- All imports must use @/ alias
- TypeScript strict mode

Please analyze the Lovable codebase and provide a migration plan, then execute the migration step by step.
```

## 🔀 Étape 4 : Fusion avec structure existante

### 4.1 Copier les pages Lovable

```bash
# Depuis le dossier lovable-import
cp -r src/pages/* ../lovable-app/src/pages/
# OU sur Windows
xcopy /E /I src\pages lovable-app\src\pages
```

### 4.2 Copier les composants Lovable

```bash
# Vérifier les conflits avant de copier
cp -r src/components/* ../lovable-app/src/components/
```

### 4.3 Mettre à jour le router (App.tsx)

```typescript
// Ajouter les nouvelles routes Lovable
import NewLovablePage from "./pages/NewLovablePage";

<Routes>
  <Route path="/" element={<Index />} />
  <Route path="/upload" element={<UploadPage />} />
  <Route path="/lovable-page" element={<NewLovablePage />} />
  {/* Autres routes Lovable */}
</Routes>
```

## 🛠️ Étape 5 : Corrections post-migration

### 5.1 Vérifier les imports

```bash
# Rechercher les imports incorrects
grep -r "from '@/components" lovable-app/src/
grep -r "import.*from.*\.\./" lovable-app/src/
```

### 5.2 Corriger les alias

Remplacer tous les imports relatifs par des alias `@/` :

```typescript
// ❌ Avant (Lovable)
import { Button } from "../../components/ui/button"

// ✅ Après (Cursor)
import { Button } from "@/components/ui/button"
```

### 5.3 Vérifier Tailwind

```bash
# Vérifier que toutes les classes Tailwind sont valides
npm run build
```

### 5.4 Vérifier TypeScript

```bash
# Vérifier les erreurs TypeScript
npm run build
# OU
npx tsc --noEmit
```

## 📦 Étape 6 : Dépendances

### Vérifier package.json

```bash
cd lovable-app
npm install
```

### Ajouter les dépendances manquantes

Si des dépendances Lovable sont manquantes :

```bash
npm install [package-name]
```

## ✅ Checklist de migration

- [ ] Code Lovable importé depuis GitHub
- [ ] Pages Lovable copiées dans `lovable-app/src/pages/`
- [ ] Composants Lovable copiés dans `lovable-app/src/components/`
- [ ] Router mis à jour dans `App.tsx`
- [ ] Imports corrigés (alias `@/`)
- [ ] Design purple conservé
- [ ] Shadcn components utilisés
- [ ] Backend API compatible (`/api/upload`)
- [ ] TypeScript sans erreurs
- [ ] Tailwind config compatible
- [ ] Tests fonctionnels

## 🐛 Résolution de problèmes

### Erreur "Cannot find module '@/components'"

**Solution** : Vérifier `tsconfig.app.json` :
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

### Erreur Tailwind classes

**Solution** : Vérifier `tailwind.config.js` contient tous les chemins :
```js
content: [
  './src/**/*.{ts,tsx}',
  './pages/**/*.{ts,tsx}',
  // ...
]
```

### Conflits de noms de fichiers

**Solution** : Renommer les fichiers en conflit :
```bash
# Exemple
mv UploadPage.tsx UploadPageLovable.tsx
```

### Erreurs TypeScript

**Solution** : Vérifier les types et ajouter les types manquants :
```bash
npm install --save-dev @types/[package-name]
```

## 🎯 Intégration avec Backend

### Vérifier la compatibilité API

Le backend existant (`backend/main.py`) expose :
- `POST /api/upload` : Upload CSV MyChron → JSON avec score/analyses

Les pages Lovable doivent utiliser cette API :
```typescript
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

fetch(`${API_URL}/api/upload`, {
  method: "POST",
  body: formData
})
```

## 📚 Ressources

- [Cursor Documentation](https://cursor.sh/docs)
- [Shadcn UI](https://ui.shadcn.com)
- [Tailwind CSS](https://tailwindcss.com)
- [React Router](https://reactrouter.com)

---

**Migration ApexAI** 🏎️
