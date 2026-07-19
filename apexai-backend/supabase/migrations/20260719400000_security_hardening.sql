-- Apex AI — Sprint 0 : durcissement sécurité (correctifs advisors Supabase)
-- DÉJÀ APPLIQUÉ en prod via MCP le 2026-07-19 — versionné ici pour traçabilité.
-- Idempotent.

-- 1. search_path immuable sur la fonction trigger (lint 0011)
ALTER FUNCTION public.update_modified_column() SET search_path = '';

-- 2. Les fonctions SECURITY DEFINER ne doivent pas être appelables via l'API
--    REST par anon/authenticated (lints 0028/0029). Les triggers continuent
--    de fonctionner (exécution en tant que propriétaire de table).
REVOKE EXECUTE ON FUNCTION public.handle_new_user() FROM anon, authenticated, public;
REVOKE EXECUTE ON FUNCTION public.profiles_protect_subscription_columns() FROM anon, authenticated, public;

-- Notes restantes (actions manuelles dashboard, non SQL) :
--   - Auth > Passwords : activer "Leaked password protection" (HaveIBeenPwned)
--   - Storage > avatars : policy SELECT large permet le listing du bucket
--     public (les URLs publiques n'en ont pas besoin) — à restreindre si
--     les listings ne sont pas utilisés par l'app.
