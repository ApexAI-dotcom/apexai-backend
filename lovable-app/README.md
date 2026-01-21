# Apex AI - Web App

Application React/TypeScript pour l'analyse de télémétrie karting avec IA.

## 🚀 Installation

### 1. Installer les dépendances

```bash
npm install
```

### 2. Installer les dépendances supplémentaires pour shadcn-ui

```bash
npm install clsx tailwind-merge class-variance-authority tailwindcss-animate
```

### 3. Configuration de l'API

Créez un fichier `.env` à la racine du projet :

```env
VITE_API_URL=http://localhost:8000
```

### 4. Lancer le serveur de développement

```bash
npm run dev
```

L'application sera disponible sur `http://localhost:5173`

## 📁 Structure du projet

```
lovable-app/
├── src/
│   ├── components/
│   │   └── ui/          # Composants shadcn-ui
│   ├── lib/
│   │   ├── api.ts       # Client API
│   │   └── utils.ts     # Utilitaires
│   ├── pages/
│   │   └── UploadPage.tsx  # Page d'upload
│   ├── App.tsx
│   └── main.tsx
├── components.json      # Configuration shadcn-ui
├── tailwind.config.js   # Configuration Tailwind
└── vite.config.ts       # Configuration Vite
```

## 🎨 Fonctionnalités

- ✅ Upload de fichiers CSV (drag & drop)
- ✅ Analyse de télémétrie via API Python
- ✅ Affichage du score de performance /100
- ✅ Conseils de coaching personnalisés
- ✅ Design moderne avec glassmorphism
- ✅ Animations avec Framer Motion
- ✅ Notifications avec Sonner

## 🔧 Technologies

- **React 19** + **TypeScript**
- **Vite** - Build tool
- **Tailwind CSS** - Styling
- **shadcn-ui** - Composants UI
- **Framer Motion** - Animations
- **React Router** - Routing
- **Sonner** - Notifications

## 📝 Notes

- Assurez-vous que l'API Python est démarrée sur `http://localhost:8000`
- Les fichiers CSV doivent contenir des colonnes GPS (Latitude, Longitude, Speed)
