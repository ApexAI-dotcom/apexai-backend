# RLS ApexAI — Base de données et Row Level Security

**Domaine :** `supabase/migrations/**` + `docs/RLS*.md`  
**Commit :** `DB-###: [table/policy/doc]`

---

## Règles obligatoires

### RLS

- **SELECT / INSERT / UPDATE** : `WHERE auth.uid() = user_id`
- Toutes les tables métier avec données par utilisateur exposent une politique RLS basée sur `user_id`.

### Tables

- Colonne **`user_id`** : FK → `public.profiles(id)` (UUID)
- `profiles.id` = identifiant utilisateur (lien avec `auth.users` selon setup Supabase).

### Migrations

- Nom : **timestamp + description** (ex. `20260102000000_add_profiles_subscription_and_usage_logs.sql`)
- Contenu : schéma + **RLS inclus** (ENABLE ROW LEVEL SECURITY + politiques).

---

## État actuel

### Table `public.profiles`

- Référence utilisateur : `id` (PK, UUID).
- Colonnes abonnement (Stripe, tier, compteur analyses) ajoutées par migration.
- Protection des colonnes abonnement côté client : trigger `protect_profiles_subscription_columns` (seul le backend en `service_role` peut les modifier).

### Table `public.usage_logs`

| Colonne   | Type        | Contrainte              |
|----------|-------------|--------------------------|
| id       | UUID        | PK, DEFAULT gen_random_uuid() |
| user_id  | UUID        | NOT NULL, FK → profiles(id) ON DELETE CASCADE |
| action   | TEXT        | NOT NULL                 |
| created_at | TIMESTAMPTZ | NOT NULL, DEFAULT now() |
| metadata | JSONB       |                          |

**RLS :**

- **SELECT** : `USING (auth.uid() = user_id)`
- **INSERT** : `WITH CHECK (auth.uid() = user_id)`
- **UPDATE / DELETE** : volontairement absents (logs d’audit immuables ; le backend peut agir en `service_role` si besoin).

---

## Conventions

1. **Nouvelles tables avec données par utilisateur** : ajouter `user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE`, index sur `user_id`, puis RLS SELECT/INSERT (et UPDATE si le métier le demande).
2. **Politiques** : nommer clairement (ex. `"Users can view own usage logs"`).
3. **Ne pas** mettre de code app, frontend ou API routes dans les migrations ni dans ce doc.
