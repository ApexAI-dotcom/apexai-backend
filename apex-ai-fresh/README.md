# 🏎️ APEX AI - Analyse de Télémétrie Karting avec IA

Système complet d'analyse de télémétrie karting avec intelligence artificielle pour améliorer les performances sur circuit.

## 🚀 Démarrage Rapide

### Prérequis

- **Node.js 18+**
- **npm** ou **yarn**

### Installation

```bash
npm install
```

### Démarrage

```bash
npm run dev
```

L'application sera disponible sur **http://localhost:8080**

### Build Production

```bash
npm run build
npm run preview
```

## 📁 Structure du Projet

```
apex-ai-fresh/
├── src/
│   ├── pages/              # Pages de l'application
│   │   ├── Index.tsx       # Page d'accueil
│   │   ├── Upload.tsx     # Upload CSV
│   │   ├── Dashboard.tsx   # Tableau de bord
│   │   ├── Pricing.tsx     # Tarifs
│   │   ├── Profile.tsx     # Profil utilisateur
│   │   └── NotFound.tsx    # Page 404
│   │
│   ├── components/         # Composants React
│   │   ├── ui/            # Composants Shadcn UI
│   │   ├── layout/        # Layout, Navbar, MobileNav
│   │   ├── stats/         # ScoreCard, StatCard
│   │   ├── racing/        # ApexGraph
│   │   ├── pricing/       # PricingCard
│   │   └── upload/        # CSVUploader
│   │
│   ├── hooks/             # Hooks React personnalisés
│   ├── assets/            # Ressources statiques
│   ├── App.tsx            # Composant principal + Router
│   ├── main.tsx           # Point d'entrée React
│   └── index.css          # Styles globaux Tailwind
│
├── public/                # Fichiers publics
├── package.json           # Dépendances npm
├── vite.config.ts         # Configuration Vite
├── tailwind.config.ts     # Configuration Tailwind
└── tsconfig.json          # Configuration TypeScript
```

## 🎯 Fonctionnalités

- ✅ **Page d'accueil** : Hero section avec présentation
- ✅ **Upload CSV** : Drag & drop avec preview
- ✅ **Dashboard** : Visualisation des statistiques
- ✅ **Pricing** : Page tarifs
- ✅ **Profile** : Profil utilisateur
- ✅ **Design Purple** : Glassmorphism moderne

## 🛠️ Stack Technique

- **Framework** : React 18.3.1
- **Build** : Vite 5.4.19
- **Router** : React Router DOM 6.30.1
- **UI** : Shadcn UI + Tailwind CSS 3.4.17
- **Icons** : Lucide React
- **Animations** : Framer Motion
- **State** : React Query + React Hooks
- **Forms** : React Hook Form + Zod

## 📦 Scripts Disponibles

- `npm run dev` - Démarre le serveur de développement
- `npm run build` - Build production
- `npm run preview` - Preview du build production
- `npm run lint` - Linter le code
- `npm test` - Lance les tests
- `npm run test:watch` - Tests en mode watch

## 🔧 Configuration

### Variables d'Environnement

Créer un fichier `.env` à la racine :

```env
VITE_API_URL=http://localhost:8000
```

### Port

Le serveur démarre par défaut sur le port **8080**. Modifier dans `vite.config.ts` si nécessaire.

## 📝 Routes Disponibles

- `/` - Page d'accueil
- `/upload` - Upload CSV MyChron
- `/dashboard` - Tableau de bord
- `/pricing` - Tarifs
- `/profile` - Profil utilisateur
- `/*` - Page 404 (NotFound)

## 🐛 Résolution de Problèmes

### Port déjà utilisé

Modifier le port dans `vite.config.ts` :
```typescript
server: {
  port: 3000, // Changer le port
}
```

### Erreur "Cannot find module '@/components'"

Vérifier `tsconfig.json` :
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

## 📚 Documentation

- [Structure du Projet](../PROJECT_STRUCTURE.md)
- [Guide Démarrage Backend](../BACKEND_STARTUP.md)
- [Documentation API](../README_API.md)

## 📄 Licence

© 2024 APEX AI. Tous droits réservés.

---

**APEX AI** 🏎️ - *Ton Coach Virages IA*
