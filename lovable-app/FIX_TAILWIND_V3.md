# 🚨 FIX URGENT - Downgrade Tailwind v3 + Fix Shadcn

## ⚡ Commandes à exécuter (dans l'ordre)

### 1. Aller dans le dossier lovable-app
```bash
cd lovable-app
```

### 2. Désinstaller Tailwind v4
```bash
npm uninstall @tailwindcss/vite
```

### 3. Installer Tailwind v3 + PostCSS
```bash
npm install -D tailwindcss@^3.4.0 postcss autoprefixer
```

### 4. Initialiser Tailwind (crée tailwind.config.js et postcss.config.js)
```bash
npx tailwindcss init -p
```

**Note:** Les fichiers sont déjà créés avec la bonne config, mais cette commande vérifie que tout est OK.

### 5. Nettoyer le cache
```bash
rm -rf node_modules/.vite
# Sur Windows : rmdir /s /q node_modules\.vite
```

### 6. Lancer le serveur de développement
```bash
npm run dev
```

L'application sera disponible sur : **http://localhost:3000**

## ✅ Fichiers modifiés

1. ✅ `vite.config.ts` - Retiré `@tailwindcss/vite`, gardé seulement `react()` + alias `@`
2. ✅ `tailwind.config.js` - Utilise `module.exports` (format v3) avec thème Shadcn complet
3. ✅ `src/index.css` - Utilise `@tailwind base/components/utilities` + CSS vars + @layer base
4. ✅ `postcss.config.js` - Créé avec tailwindcss + autoprefixer

## 🔍 Vérifications

- ✅ `vite.config.ts` n'importe plus `@tailwindcss/vite`
- ✅ `tailwind.config.js` utilise `module.exports` (pas `export default`)
- ✅ `src/index.css` commence par `@tailwind base/components/utilities`
- ✅ `postcss.config.js` existe avec tailwindcss + autoprefixer
- ✅ Port 3000 configuré dans `vite.config.ts`

## 📝 Différences v3 vs v4

### Tailwind v3 (actuel)
- Utilise PostCSS (`postcss.config.js`)
- Syntaxe `@tailwind base/components/utilities`
- Config avec `module.exports`
- Plugin Vite non nécessaire

### Tailwind v4 (ancien)
- Utilise plugin Vite (`@tailwindcss/vite`)
- Syntaxe `@import "tailwindcss"`
- Config avec `export default`
- Pas besoin de PostCSS

## 🐛 Si erreurs persistent

### Erreur "Cannot find module 'tailwindcss'"
```bash
npm install -D tailwindcss@^3.4.0 postcss autoprefixer
```

### Erreur "border-border"
Vérifiez que `tailwind.config.js` contient bien :
```js
colors: {
  border: "hsl(var(--border))",
  // ...
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
