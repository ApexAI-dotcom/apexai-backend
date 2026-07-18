-- Apex AI — Migration: stocker la signature de piste dans les logs de session
-- Contexte : le chemin "Depuis la télémétrie > Sessions récentes" lisait
--            kart_session_logs qui ne stocke aucune caractéristique de piste,
--            d'où des valeurs génériques systématiques (mixte/2 épingles/3 courbes).
--            On stocke désormais la signature calculée au moment de l'analyse.
-- Idempotent.

ALTER TABLE public.kart_session_logs
    ADD COLUMN IF NOT EXISTS track_features JSONB;
