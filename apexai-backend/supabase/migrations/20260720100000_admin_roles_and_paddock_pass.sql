-- Apex AI — Sprint 3 : back-office (rôles) + Paddock Pass 24h
-- DÉJÀ APPLIQUÉ en prod via MCP — versionné pour traçabilité. Idempotent.

-- ─────────────────────────────────────────────
-- 1. Rôles d'administration (délégation collaborateurs)
--    owner   : tout, y compris la gestion des rôles
--    admin   : tout sauf la gestion des rôles
--    support : retours pilotes + lecture des stats
--    analyst : lecture des stats uniquement
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.admin_roles (
    user_id    UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    role       TEXT NOT NULL CHECK (role IN ('owner','admin','support','analyst')),
    granted_by UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    note       TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.admin_roles ENABLE ROW LEVEL SECURITY;
-- Aucune policy : table pilotée exclusivement par le backend (service_role).

DROP TRIGGER IF EXISTS update_admin_roles_modtime ON public.admin_roles;
CREATE TRIGGER update_admin_roles_modtime
BEFORE UPDATE ON public.admin_roles
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

INSERT INTO public.admin_roles (user_id, role, note)
SELECT id, 'owner', 'Compte fondateur'
FROM auth.users WHERE lower(email) = 'moreauy58@gmail.com'
ON CONFLICT (user_id) DO UPDATE SET role = 'owner';

-- ─────────────────────────────────────────────
-- 2. Paddock Pass : codes + activations
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.promo_codes (
    code            TEXT PRIMARY KEY,
    label           TEXT,
    tier            TEXT NOT NULL DEFAULT 'racer' CHECK (tier IN ('racer','team')),
    duration_hours  INTEGER NOT NULL DEFAULT 24 CHECK (duration_hours > 0),
    max_redemptions INTEGER,
    redemptions     INTEGER NOT NULL DEFAULT 0,
    expires_at      TIMESTAMPTZ,
    active          BOOLEAN NOT NULL DEFAULT true,
    created_by      UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.promo_redemptions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code        TEXT NOT NULL REFERENCES public.promo_codes(code) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    trial_until TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (code, user_id)   -- un code ne peut être utilisé qu'une fois par pilote
);
CREATE INDEX IF NOT EXISTS idx_promo_redemptions_user ON public.promo_redemptions (user_id, created_at DESC);

ALTER TABLE public.promo_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.promo_redemptions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users read their own redemptions" ON public.promo_redemptions;
CREATE POLICY "Users read their own redemptions"
    ON public.promo_redemptions FOR SELECT USING (auth.uid() = user_id);

-- Essai temporaire : ADDITIF, ne touche à aucune colonne Stripe existante.
-- Tier effectif = tier Stripe OU trial_tier si trial_until est dans le futur.
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS trial_tier  TEXT;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS trial_until TIMESTAMPTZ;
