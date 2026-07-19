-- Apex AI — Migration: notion de "pneu monté" sur le kart
-- Un seul train peut être monté à la fois (is_mounted). Il pilote l'affichage
-- dans l'identité du kart et sert de base au calcul des pressions + à la
-- détection d'un changement de pneu recommandé.
-- Idempotent.

ALTER TABLE public.kart_tire_sets
    ADD COLUMN IF NOT EXISTS is_mounted BOOLEAN NOT NULL DEFAULT false;

-- Par défaut : monter le premier train slick actif de chaque pilote
-- (uniquement s'il n'a encore aucun train monté).
UPDATE public.kart_tire_sets t
SET is_mounted = true
WHERE t.id = (
    SELECT id FROM public.kart_tire_sets
    WHERE user_id = t.user_id AND active = true AND is_rain = false
    ORDER BY created_at ASC
    LIMIT 1
)
AND NOT EXISTS (
    SELECT 1 FROM public.kart_tire_sets m
    WHERE m.user_id = t.user_id AND m.is_mounted = true
);
