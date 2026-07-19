-- Apex AI — Migration: expansion du catalogue kart_components
--   1. Intervalles d'entretien usuels constructeur sur les moteurs existants
--   2. Cibles de pression à chaud sur les pneus existants
--   3. Entretien freins / châssis
--   4. Nouveaux composants (moteurs, châssis, axes OTK réels)
-- Valeurs = usages courants compétition documentés publiquement, à affiner
-- avec les manuels constructeur officiels ("source":"baseline").
-- Idempotent : merge JSONB + ON CONFLICT DO NOTHING.

-- ─────────────────────────────────────────────
-- 1. Entretien moteurs (heures entre interventions, usage compétition courant)
-- ─────────────────────────────────────────────
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"top_end_h":10,"full_rebuild_h":20,"note":"Piston ~10h, réfection complète ~20h (usage compétition)"}}'::jsonb WHERE id IN ('iame-x30','iame-x30-junior');
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"top_end_h":8,"full_rebuild_h":16,"note":"175cc plus sollicité : piston ~8h"}}'::jsonb WHERE id = 'iame-super-x30';
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"top_end_h":25,"full_rebuild_h":50,"note":"Rotax : intervalles longs, ~25h compétition / 50h loisir"}}'::jsonb WHERE id IN ('rotax-max-125','rotax-dd2','rotax-junior');
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"top_end_h":50,"full_rebuild_h":100,"note":"Catégories Micro/Mini bridées : usure réduite"}}'::jsonb WHERE id IN ('rotax-micro','rotax-mini');
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"top_end_h":20,"full_rebuild_h":40,"note":"KA100 refroidi air : piston ~20-25h"}}'::jsonb WHERE id = 'iame-ka100';
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"top_end_h":4,"full_rebuild_h":10,"note":"KZ : piston toutes les ~3-5h, réfection ~10h"}}'::jsonb WHERE id IN ('tm-r1','tm-r2','tm-kz10c','vortex-rvx');
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"top_end_h":15,"full_rebuild_h":30}}'::jsonb WHERE id = 'vortex-rok';
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"oil_change_h":20,"full_rebuild_h":300,"note":"4 temps : vidange ~20h, longévité très élevée"}}'::jsonb WHERE id IN ('honda-gx160','honda-gx270','honda-gx390','subaru-kx21');
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"top_end_h":15,"full_rebuild_h":30}}'::jsonb WHERE id = 'iame-water-swift';

-- ─────────────────────────────────────────────
-- 2. Pneus : cible de pression à chaud (bar) par gomme
-- ─────────────────────────────────────────────
UPDATE public.kart_components SET specs = specs || '{"target_hot_bar":[0.80,0.95]}'::jsonb WHERE category='tire' AND subcategory='Soft';
UPDATE public.kart_components SET specs = specs || '{"target_hot_bar":[0.85,1.00]}'::jsonb WHERE category='tire' AND subcategory='Medium';
UPDATE public.kart_components SET specs = specs || '{"target_hot_bar":[0.90,1.05]}'::jsonb WHERE category='tire' AND subcategory='Hard';
UPDATE public.kart_components SET specs = specs || '{"target_hot_bar":[1.15,1.35]}'::jsonb WHERE category='tire' AND subcategory='Wet';

-- ─────────────────────────────────────────────
-- 3. Entretien freins et châssis
-- ─────────────────────────────────────────────
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"pads_check_laps":300,"fluid_change_months":12,"note":"Contrôle plaquettes ~300 tours, purge liquide annuelle"}}'::jsonb WHERE category='brake';
UPDATE public.kart_components SET specs = specs || '{"maintenance":{"note":"Contrôle géométrie et fissures après chaque contact, serrage visserie chaque week-end de course"}}'::jsonb WHERE category='chassis';

-- ─────────────────────────────────────────────
-- 4. Nouveaux composants
-- ─────────────────────────────────────────────

-- Moteurs supplémentaires
INSERT INTO public.kart_components (id, category, brand, name, subcategory, default_life, life_unit, specs) VALUES
  ('iame-mini-swift', 'engine', 'IAME',   'Mini Swift 60cc', 'Mini',       20, 'hours', '{"displacement_cc":60,"stroke":"2T","cooling":"liquide","maintenance":{"top_end_h":15,"full_rebuild_h":30}}'),
  ('vortex-mini-rok', 'engine', 'Vortex', 'Mini ROK 60cc',   'Mini',       20, 'hours', '{"displacement_cc":60,"stroke":"2T","cooling":"liquide","maintenance":{"top_end_h":15,"full_rebuild_h":30}}'),
  ('vortex-rok-junior','engine','Vortex', 'ROK Junior',      'Junior',     15, 'hours', '{"displacement_cc":125,"stroke":"2T","cooling":"liquide","restricted":true,"maintenance":{"top_end_h":15,"full_rebuild_h":30}}'),
  ('honda-gx200',     'engine', 'Honda',  'GX200',           '4 Temps',   100, 'hours', '{"displacement_cc":196,"stroke":"4T","cooling":"air","maintenance":{"oil_change_h":20,"full_rebuild_h":300}}')
ON CONFLICT (id) DO NOTHING;

-- Châssis supplémentaires (marques majeures)
INSERT INTO public.kart_components (id, category, brand, name, subcategory, specs) VALUES
  ('exprit-noesis-r',   'chassis', 'Exprit',       'Noesis R',   '30mm', '{"tubes_mm":30,"group":"OTK","maintenance":{"note":"Contrôle géométrie après chaque contact"}}'),
  ('praga-dragon',      'chassis', 'Praga',        'Dragon',     '30mm', '{"tubes_mm":30,"maintenance":{"note":"Contrôle géométrie après chaque contact"}}'),
  ('intrepid-cruiser',  'chassis', 'Intrepid',     'Cruiser',    '30mm', '{"tubes_mm":30,"maintenance":{"note":"Contrôle géométrie après chaque contact"}}'),
  ('energy-kinetic',    'chassis', 'Energy Corse', 'Kinetic',    '30mm', '{"tubes_mm":30,"maintenance":{"note":"Contrôle géométrie après chaque contact"}}')
ON CONFLICT (id) DO NOTHING;

-- Axes arrière OTK (grades réels, 50mm) — la dureté pilote le grip arrière
INSERT INTO public.kart_components (id, category, brand, name, subcategory, specs) VALUES
  ('otk-axle-q', 'axle', 'OTK', 'Axe Q (souple)',   'Souple', '{"diameter_mm":50,"grade":"Q","effect":"Plus de grip arrière — piste froide, glissante ou pluie"}'),
  ('otk-axle-m', 'axle', 'OTK', 'Axe M (standard)', 'Medium', '{"diameter_mm":50,"grade":"M","effect":"Réglage de base polyvalent"}'),
  ('otk-axle-h', 'axle', 'OTK', 'Axe H (dur)',      'Dur',    '{"diameter_mm":50,"grade":"H","effect":"Libère l''arrière — piste gommée, chaude, fort grip"}')
ON CONFLICT (id) DO NOTHING;
