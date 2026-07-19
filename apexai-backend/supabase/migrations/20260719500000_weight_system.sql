-- Apex AI — Sprint 1 : système d'estimation de poids
-- 1. Poids pilote persistant dans le profil (équipement compris)
-- 2. Poids constructeur des composants dans le catalogue (specs.weight_kg)
--    Sources : fiches techniques publiées (Honda documente ses poids à sec),
--    valeurs usuelles constructeur pour les 2T ("source":"baseline").
-- DÉJÀ APPLIQUÉ en prod via MCP — versionné pour traçabilité. Idempotent.

ALTER TABLE public.kart_profiles
    ADD COLUMN IF NOT EXISTS driver_weight_kg NUMERIC(5, 1);

-- Moteurs 125cc 2T (~17-18 kg complets), KZ (~19 kg), 60cc Mini (~10 kg)
UPDATE public.kart_components SET specs = specs || '{"weight_kg":17}'::jsonb
WHERE id IN ('rotax-micro','rotax-mini','rotax-junior','rotax-max-125','iame-x30','iame-x30-junior','vortex-rok','vortex-rok-junior');
UPDATE public.kart_components SET specs = specs || '{"weight_kg":21}'::jsonb WHERE id = 'rotax-dd2';
UPDATE public.kart_components SET specs = specs || '{"weight_kg":18}'::jsonb WHERE id = 'iame-super-x30';
UPDATE public.kart_components SET specs = specs || '{"weight_kg":14}'::jsonb WHERE id = 'iame-ka100';
UPDATE public.kart_components SET specs = specs || '{"weight_kg":19}'::jsonb
WHERE id IN ('tm-r1','tm-r2','tm-kz10c','vortex-rvx');
UPDATE public.kart_components SET specs = specs || '{"weight_kg":10}'::jsonb
WHERE id IN ('iame-water-swift','iame-mini-swift','vortex-mini-rok');
-- 4 temps : poids à sec catalogue Honda
UPDATE public.kart_components SET specs = specs || '{"weight_kg":15.1}'::jsonb WHERE id = 'honda-gx160';
UPDATE public.kart_components SET specs = specs || '{"weight_kg":16.1}'::jsonb WHERE id = 'honda-gx200';
UPDATE public.kart_components SET specs = specs || '{"weight_kg":25.2}'::jsonb WHERE id = 'honda-gx270';
UPDATE public.kart_components SET specs = specs || '{"weight_kg":31.5}'::jsonb WHERE id = 'honda-gx390';
UPDATE public.kart_components SET specs = specs || '{"weight_kg":14}'::jsonb WHERE id = 'subaru-kx21';

-- Châssis roulant sans moteur : ~60 kg (62 kg en KZ, freins avant)
UPDATE public.kart_components SET specs = specs || '{"weight_kg":60}'::jsonb
WHERE category = 'chassis' AND (specs->>'weight_kg') IS NULL;
UPDATE public.kart_components SET specs = specs || '{"weight_kg":62}'::jsonb
WHERE id IN ('sodi-sigma-kz');
