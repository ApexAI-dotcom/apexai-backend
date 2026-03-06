-- =============================================================================
-- Migration: colonnes abonnement Stripe sur profiles + table usage_logs
-- À exécuter dans Supabase SQL Editor (ou via Supabase CLI)
-- Ne modifie pas les colonnes existantes de profiles (ADD COLUMN uniquement).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. PROFILES : ajout des 9 colonnes abonnement (sans toucher aux existantes)
-- -----------------------------------------------------------------------------

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT,
  ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT,
  ADD COLUMN IF NOT EXISTS subscription_tier TEXT NOT NULL DEFAULT 'rookie'
    CHECK (subscription_tier IN ('rookie', 'racer', 'team')),
  ADD COLUMN IF NOT EXISTS billing_period TEXT
    CHECK (billing_period IS NULL OR billing_period IN ('monthly', 'annual')),
  ADD COLUMN IF NOT EXISTS subscription_status TEXT
    CHECK (subscription_status IS NULL OR subscription_status IN ('active', 'canceled', 'past_due', 'trialing')),
  ADD COLUMN IF NOT EXISTS subscription_start_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS subscription_end_date TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS analyses_count_current_month INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_analysis_reset_date TIMESTAMPTZ NOT NULL DEFAULT now();

-- Contrainte UNIQUE + index sur stripe_customer_id (plusieurs NULL autorisés en Postgres)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'profiles_stripe_customer_id_key'
  ) THEN
    ALTER TABLE public.profiles
      ADD CONSTRAINT profiles_stripe_customer_id_key UNIQUE (stripe_customer_id);
  END IF;
END $$;

-- (La contrainte UNIQUE crée automatiquement un index sur stripe_customer_id.)
COMMENT ON COLUMN public.profiles.stripe_customer_id IS 'ID client Stripe (unique par compte)';
COMMENT ON COLUMN public.profiles.subscription_tier IS 'rookie | racer | team - source de vérité abonnement';
COMMENT ON COLUMN public.profiles.analyses_count_current_month IS 'Compteur analyses du mois en cours, réinitialisé selon last_analysis_reset_date';

-- -----------------------------------------------------------------------------
-- 2. RLS PROFILES : le service_role bypass RLS (Supabase). Pour empêcher les
--    utilisateurs authentifiés de modifier les colonnes abo depuis le client,
--    on utilise un trigger qui réinjecte les anciennes valeurs sur ces colonnes.
-- -----------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.profiles_protect_subscription_columns()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  -- Seuls les utilisateurs authentifiés (role = authenticated) ne peuvent pas modifier
  -- les colonnes abo. Le backend utilise service_role et peut donc les mettre à jour.
  IF current_setting('request.jwt.claim.role', true) = 'authenticated' THEN
    NEW.stripe_customer_id       := OLD.stripe_customer_id;
    NEW.stripe_subscription_id   := OLD.stripe_subscription_id;
    NEW.subscription_tier        := OLD.subscription_tier;
    NEW.billing_period           := OLD.billing_period;
    NEW.subscription_status      := OLD.subscription_status;
    NEW.subscription_start_date  := OLD.subscription_start_date;
    NEW.subscription_end_date    := OLD.subscription_end_date;
    NEW.analyses_count_current_month := OLD.analyses_count_current_month;
    NEW.last_analysis_reset_date := OLD.last_analysis_reset_date;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS protect_profiles_subscription_columns ON public.profiles;
CREATE TRIGGER protect_profiles_subscription_columns
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW
  EXECUTE FUNCTION public.profiles_protect_subscription_columns();

-- -----------------------------------------------------------------------------
-- 3. TABLE usage_logs
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.usage_logs (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  action     TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata   JSONB
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_user_id ON public.usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_logs_created_at ON public.usage_logs(created_at);

ALTER TABLE public.usage_logs ENABLE ROW LEVEL SECURITY;

-- Chaque utilisateur ne voit que ses propres logs
CREATE POLICY "Users can view own usage logs"
  ON public.usage_logs
  FOR SELECT
  USING (auth.uid() = user_id);

-- Les utilisateurs peuvent insérer leurs propres logs (ou le backend via service_role)
CREATE POLICY "Users can insert own usage logs"
  ON public.usage_logs
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Pas de UPDATE/DELETE pour les logs (audit immuable) ; le backend peut tout faire avec service_role si besoin.

COMMENT ON TABLE public.usage_logs IS 'Logs d''usage (analyses, exports, etc.) par utilisateur.';
