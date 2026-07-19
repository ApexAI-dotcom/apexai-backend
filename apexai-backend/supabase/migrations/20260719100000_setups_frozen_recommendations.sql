-- Apex AI — Migration: recommandations figées par réglage
-- Les recommandations générées sont sauvegardées avec le réglage et
-- restaurées telles quelles au rechargement (au lieu d'être recalculées
-- à partir des valeurs modifiées par le pilote).
-- Idempotent.

ALTER TABLE public.kart_setups
    ADD COLUMN IF NOT EXISTS recommendations JSONB;
