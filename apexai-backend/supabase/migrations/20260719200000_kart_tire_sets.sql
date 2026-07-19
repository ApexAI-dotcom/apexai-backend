-- Apex AI — Migration: stock de trains de pneus (Mon Kart)
-- Chaque ligne = un train complet (4 pneus). Le pilote déclare ses trains
-- (Train 1 Neuf, Train 2 Rodé, Train Pluie...), ApexAI recommande ensuite
-- le train adapté à la session (warm-up / qualif / course × météo).
-- Migration douce : le pneu actuel du profil devient automatiquement "Train 1".
-- Idempotent.

CREATE TABLE IF NOT EXISTS public.kart_tire_sets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    label        TEXT NOT NULL,                     -- "Train 1", "Train Pluie"...
    component_id TEXT REFERENCES public.kart_components(id) ON DELETE SET NULL,
    custom_model TEXT,                              -- libellé libre si hors catalogue
    state        TEXT NOT NULL DEFAULT 'neuf' CHECK (state IN ('neuf', 'rode', 'use')),
    is_rain      BOOLEAN NOT NULL DEFAULT false,
    laps_current INTEGER NOT NULL DEFAULT 0,
    laps_life    INTEGER NOT NULL DEFAULT 250,
    active       BOOLEAN NOT NULL DEFAULT true,     -- false = train retiré du stock
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_kart_tire_sets_user ON public.kart_tire_sets (user_id);

ALTER TABLE public.kart_tire_sets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users manage their own tire sets" ON public.kart_tire_sets;
CREATE POLICY "Users manage their own tire sets"
    ON public.kart_tire_sets FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- updated_at automatique (réutilise la fonction créée par add_kart_tables)
DROP TRIGGER IF EXISTS update_kart_tire_sets_modtime ON public.kart_tire_sets;
CREATE TRIGGER update_kart_tire_sets_modtime
BEFORE UPDATE ON public.kart_tire_sets
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

-- Migration douce : le pneu déclaré dans le profil devient "Train 1"
-- (état estimé d'après l'usure, pluie détectée par le libellé)
INSERT INTO public.kart_tire_sets (user_id, label, custom_model, state, is_rain, laps_current, laps_life)
SELECT
    p.user_id,
    'Train 1',
    p.tires_model,
    CASE
        WHEN COALESCE(p.tires_laps_current, 0) = 0 THEN 'neuf'
        WHEN COALESCE(p.tires_laps_current, 0) < 60 THEN 'rode'
        ELSE 'use'
    END,
    (p.tires_model ILIKE '%pluie%' OR p.tires_model ILIKE '%wet%' OR p.tires_model ILIKE '%rain%'),
    COALESCE(p.tires_laps_current, 0),
    COALESCE(NULLIF(p.tires_laps_life, 0), 250)
FROM public.kart_profiles p
WHERE p.tires_model IS NOT NULL AND p.tires_model <> ''
  AND NOT EXISTS (SELECT 1 FROM public.kart_tire_sets t WHERE t.user_id = p.user_id);
