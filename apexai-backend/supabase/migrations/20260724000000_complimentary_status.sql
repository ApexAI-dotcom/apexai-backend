-- Apex AI — Statut d'abonnement "complimentary" (accès offert, non facturé)
-- Permet de donner un accès Premium à un compte (fondateur, partenaire...)
-- proprement en base, au lieu d'un forçage codé en dur côté frontend.
-- DÉJÀ APPLIQUÉ en prod via MCP — versionné pour traçabilité. Idempotent.

ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS profiles_subscription_status_check;
ALTER TABLE public.profiles ADD CONSTRAINT profiles_subscription_status_check
  CHECK (
    subscription_status IS NULL
    OR subscription_status = ANY (ARRAY['active','canceled','past_due','trialing','complimentary']::text[])
  );
