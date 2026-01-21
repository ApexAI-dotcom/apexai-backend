# 🔧 FIX URGENT - Instructions de correction

## ⚡ Commandes à exécuter (dans l'ordre)

### 1. Aller dans le dossier lovable-app
```bash
cd lovable-app
```

### 2. Installer toutes les dépendances manquantes
```bash
npm install class-variance-authority clsx tailwind-merge tailwindcss-animate
```

### 3. Vérifier que tout est installé
```bash
npm list class-variance-authority clsx tailwind-merge tailwindcss-animate tailwindcss-animate
```

### 4. Nettoyer le cache si nécessaire
```bash
rm -rf node_modules/.vite
```

### 5. Lancer le serveur de développement sur le port 3000
```bash
npm run dev
```

L'application sera disponible sur : **http://localhost:3000**

## ✅ Vérifications

- ✅ `vite.config.ts` configuré avec port 3000 et alias `@`
- ✅ `postcss.config.js` configuré correctement
- ✅ `index.css` avec directives `@tailwind` correctes
- ✅ `package.json` mis à jour avec toutes les dépendances

## 🐛 Si erreurs persistent

### Erreur "Cannot find module '@/lib/utils'"
Vérifiez que `tsconfig.app.json` contient :
```json
"paths": {
  "@/*": ["./src/*"]
}
```

### Erreur PostCSS
Vérifiez que `postcss.config.js` existe et contient :
```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

### Port déjà utilisé
Si le port 3000 est occupé, Vite utilisera automatiquement 3001, 3002, etc.

## 📝 Fichiers modifiés

1. ✅ `package.json` - Ajout des dépendances manquantes
2. ✅ `vite.config.ts` - Configuration port 3000 + alias + PostCSS
3. ✅ `postcss.config.js` - Déjà correct
4. ✅ `src/index.css` - Déjà correct avec @tailwind
