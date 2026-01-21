# Instructions d'installation - Apex AI Web App

## 📦 Étape 1 : Installer les dépendances de base

```bash
npm install
```

## 📦 Étape 2 : Installer les dépendances shadcn-ui

```bash
npm install clsx tailwind-merge class-variance-authority tailwindcss-animate
```

## ⚙️ Étape 3 : Configuration

### Créer le fichier `.env`

Créez un fichier `.env` à la racine de `lovable-app/` :

```env
VITE_API_URL=http://localhost:8000
```

## 🚀 Étape 4 : Démarrer l'application

```bash
npm run dev
```

L'application sera disponible sur `http://localhost:5173`

## ✅ Vérification

1. ✅ Tailwind CSS configuré avec glassmorphism
2. ✅ shadcn-ui initialisé
3. ✅ Composants UI créés (Button, Card, Input)
4. ✅ Page Upload avec appel API
5. ✅ Design moderne avec animations

## 🔍 Dépannage

### Erreur "Cannot find module '@/lib/utils'"

Vérifiez que `tsconfig.app.json` contient bien les paths :
```json
"paths": {
  "@/*": ["./src/*"]
}
```

### Erreur "tailwindcss-animate not found"

Installez la dépendance :
```bash
npm install tailwindcss-animate
```

### L'API ne répond pas

1. Vérifiez que l'API Python est démarrée : `python run_api.py`
2. Vérifiez l'URL dans `.env` : `VITE_API_URL=http://localhost:8000`
3. Vérifiez les CORS dans l'API Python
