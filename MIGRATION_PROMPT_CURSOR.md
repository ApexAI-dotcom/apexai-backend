# 📋 Prompt Cursor Chat - Migration Lovable

## Copier ce prompt dans Cursor Chat (Ctrl+L)

```
This project was built in Lovable.dev and needs to be migrated to Cursor.

PROJECT CONTEXT:
- ApexAI: Karting telemetry analysis system
- Backend: FastAPI (Python) - analyzes MyChron CSV files via POST /api/upload
- Frontend: React + TypeScript + Tailwind v3 + Shadcn UI
- Design: Purple glassmorphism theme (from-purple-950, purple-500, etc.)

EXISTING STRUCTURE (DO NOT MODIFY):
- backend/main.py: FastAPI endpoint /api/upload for CSV MyChron analysis
- lovable-app/src/pages/index.tsx: Homepage with hero section (KEEP THIS)
- lovable-app/src/pages/UploadPage.tsx: CSV upload page with purple design (KEEP THIS)
- lovable-app/src/components/ui/: Shadcn components (Button, Card, Input, Progress, Spinner)
- lovable-app/src/components/layout/Layout.tsx: Layout wrapper
- lovable-app/src/lib/utils.ts: cn() utility function
- lovable-app/src/lib/api.ts: API client for backend

EXISTING FEATURES (PRESERVE):
- CSV MyChron upload and parsing
- Performance score calculation (/100)
- Analysis metrics (CBV, Chroma, Trajectoire, Vitesse)
- Purple glassmorphism UI design
- Framer Motion animations
- React Router with / and /upload routes

MIGRATION TASKS:
1. Analyze the imported Lovable codebase structure
2. Identify all Lovable pages (in src/pages/ or src/app/)
3. Identify all Lovable components (in src/components/)
4. Copy Lovable pages to lovable-app/src/pages/ (MERGE, don't overwrite existing)
5. Copy Lovable components to lovable-app/src/components/ (MERGE, don't overwrite existing)
6. Update App.tsx router to include all Lovable routes (ADD routes, keep existing)
7. Fix all imports to use @/ aliases (not relative paths like ../../)
8. Ensure Shadcn UI components are used (from @/components/ui/)
9. Maintain purple glassmorphism design theme throughout
10. Ensure compatibility with backend API (/api/upload endpoint)
11. Fix TypeScript errors
12. Ensure Tailwind classes are compatible with tailwind.config.js

CRITICAL CONSTRAINTS:
- KEEP existing UploadPage.tsx and index.tsx unchanged
- KEEP existing backend/main.py unchanged
- MAINTAIN purple design theme (purple-950, purple-500, purple-400, etc.)
- USE existing Shadcn components from @/components/ui/ (don't create new ones)
- PRESERVE backend API integration (POST /api/upload)
- ALL imports must use @/ alias (configured in tsconfig.app.json)
- TypeScript strict mode enabled
- Tailwind v3 (not v4)

IMPORT RULES:
- Components: import { Button } from "@/components/ui/button"
- Utils: import { cn } from "@/lib/utils"
- API: import { analyzeTelemetry } from "@/lib/api"
- Pages: import Index from "@/pages/index"

DESIGN RULES:
- Background: bg-gradient-to-br from-purple-950 via-slate-900 to-purple-950
- Cards: glass-card border-purple-500/20 backdrop-blur-xl bg-white/5
- Text primary: text-white
- Text secondary: text-slate-400
- Accent: text-purple-400, bg-purple-500/20
- Buttons: bg-gradient-to-r from-purple-600 to-pink-600

Please:
1. First analyze the codebase and identify what needs migration
2. Create a detailed migration plan
3. Execute migration step by step
4. Fix all import errors
5. Fix all TypeScript errors
6. Ensure design consistency
7. Test that existing functionality still works
8. Provide a summary of what was migrated
```

## 🎯 Utilisation

1. **Ouvrir Cursor**
2. **Ouvrir le dossier ApexAI** (File → Open Folder)
3. **Ouvrir Cursor Chat** (`Ctrl+L` ou `Cmd+L`)
4. **Coller le prompt ci-dessus**
5. **Attendre l'analyse** de Cursor
6. **Suivre les instructions** étape par étape

## 📝 Notes importantes

- Cursor analysera automatiquement votre codebase
- Il proposera des corrections pour les imports
- Il vérifiera la compatibilité TypeScript
- Il maintiendra le design purple
- Il préservera les fichiers existants

---

**Prompt optimisé pour ApexAI** 🏎️
