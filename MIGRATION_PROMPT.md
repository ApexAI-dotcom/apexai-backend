# 📋 Prompt de Migration Lovable → Cursor

## Copier ce prompt dans Cursor Chat

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
- lovable-app/src/components/ui/: Shadcn components (Button, Card, Input, Progress, Spinner)
- lovable-app/src/components/layout/Layout.tsx: Layout wrapper
- lovable-app/src/lib/utils.ts: cn() utility function
- lovable-app/src/lib/api.ts: API client for backend

EXISTING FEATURES:
- CSV MyChron upload and parsing
- Performance score calculation (/100)
- Analysis metrics (CBV, Chroma, Trajectoire, Vitesse)
- Purple glassmorphism UI design
- Framer Motion animations
- React Router with / and /upload routes

MIGRATION TASKS:
1. Review all Lovable pages and components in the imported codebase
2. Integrate Lovable pages into lovable-app/src/pages/ (keep existing index.tsx and UploadPage.tsx)
3. Integrate Lovable components into lovable-app/src/components/ (merge with existing ui/ and layout/)
4. Update App.tsx router to include all Lovable routes
5. Ensure Shadcn UI components are used consistently (don't replace with custom components)
6. Maintain purple glassmorphism design theme throughout
7. Update all imports to use @/ aliases (not relative paths)
8. Ensure compatibility with existing backend API (/api/upload endpoint)
9. Fix any TypeScript errors
10. Ensure Tailwind classes are compatible with existing tailwind.config.js
11. Preserve existing functionality (CSV upload, score display, etc.)

CONSTRAINTS:
- Keep existing UploadPage.tsx and index.tsx unchanged
- Maintain purple design theme (from-purple-950, purple-500, etc.)
- Use existing Shadcn components from @/components/ui/
- Preserve backend API integration (POST /api/upload)
- All imports must use @/ alias (configured in tsconfig.app.json)
- TypeScript strict mode enabled
- Tailwind v3 (not v4)

IMPORTANT:
- Don't break existing functionality
- Don't change the backend API structure
- Don't replace Shadcn components with custom ones
- Don't change the purple color scheme
- Merge Lovable code, don't overwrite existing code

Please:
1. First analyze the Lovable codebase structure
2. Identify what needs to be migrated
3. Create a migration plan
4. Execute the migration step by step
5. Fix any errors that arise
6. Ensure everything works together
```

## 🎯 Utilisation

1. **Ouvrir Cursor Chat** (`Ctrl+L` ou `Cmd+L`)
2. **Coller le prompt ci-dessus**
3. **Attendre l'analyse** de Cursor
4. **Suivre les instructions** de migration
5. **Vérifier** chaque étape

## 📝 Notes

- Cursor analysera automatiquement votre codebase
- Il proposera des corrections pour les imports
- Il vérifiera la compatibilité avec la structure existante
- Il maintiendra le design purple

---

**Prompt optimisé pour ApexAI** 🏎️
