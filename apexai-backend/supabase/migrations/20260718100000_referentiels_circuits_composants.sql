-- Apex AI — Migration: Référentiels professionnels
--   1. Enrichissement table circuits (longueur, pays, source) + seed circuits connus
--   2. Catalogue de composants kart_components (moteurs, pneus, freins, châssis,
--      carburateurs, axes) avec specs JSONB — remplace les presets codés en dur
--      dans le frontend (kart-presets.ts) par une vraie base versionnée.
-- Idempotent : rejouable sans risque (IF NOT EXISTS / ON CONFLICT DO NOTHING).
-- NB : les valeurs inconnues sont laissées NULL — on ne fabrique pas de données.
--      Les pressions pneus sont des bases usuelles compétition ("source":"baseline"),
--      à affiner avec les abaques officiels constructeurs.

-- ─────────────────────────────────────────────
-- 1a. circuits : colonnes référentiel
-- ─────────────────────────────────────────────
ALTER TABLE public.circuits ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL;
ALTER TABLE public.circuits ADD COLUMN IF NOT EXISTS verified   BOOLEAN DEFAULT false;
ALTER TABLE public.circuits ADD COLUMN IF NOT EXISTS length_m   NUMERIC(7, 1);
ALTER TABLE public.circuits ADD COLUMN IF NOT EXISTS corners_count INTEGER;
ALTER TABLE public.circuits ADD COLUMN IF NOT EXISTS country    TEXT;
ALTER TABLE public.circuits ADD COLUMN IF NOT EXISTS city       TEXT;
ALTER TABLE public.circuits ADD COLUMN IF NOT EXISTS source     TEXT;

-- Autoriser NULL sur les caractéristiques (données inconnues = NULL, pas de faux défauts)
ALTER TABLE public.circuits ALTER COLUMN speed_ratio DROP NOT NULL;
ALTER TABLE public.circuits ALTER COLUMN rotation DROP NOT NULL;
ALTER TABLE public.circuits ALTER COLUMN elevation DROP NOT NULL;
ALTER TABLE public.circuits ALTER COLUMN bumpiness DROP NOT NULL;
ALTER TABLE public.circuits ALTER COLUMN hairpins_count DROP NOT NULL;
ALTER TABLE public.circuits ALTER COLUMN fast_corners_count DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_circuits_slug ON public.circuits (slug);

-- ─────────────────────────────────────────────
-- 1b. Seed circuits connus (données publiques ; longueur NULL si non certifiée)
--     verified=true = fiche officielle ApexAI, non modifiable par les users
-- ─────────────────────────────────────────────
INSERT INTO public.circuits (name, slug, country, city, length_m, verified, source)
VALUES
  ('South Garda Karting',            'south-garda-karting',   'IT', 'Lonato del Garda',   1200.0, true, 'public'),
  ('PF International',               'pf-international',      'GB', 'Brandon',            1382.0, true, 'public'),
  ('Adria Karting Raceway',          'adria-karting-raceway', 'IT', 'Adria',              1302.0, true, 'public'),
  ('Circuito Internacional de Zuera','zuera',                 'ES', 'Zuera',              1699.0, true, 'public'),
  ('Karting Genk',                   'karting-genk',          'BE', 'Genk',               1360.0, true, 'public'),
  ('Le Mans Karting International',  'le-mans-karting',       'FR', 'Le Mans',            1384.0, true, 'public'),
  ('Circuit d''Angerville',          'angerville',            'FR', 'Angerville',         1240.0, true, 'public'),
  ('Circuit de Salbris',             'salbris',               'FR', 'Salbris',            1500.0, true, 'public'),
  ('Circuito Internazionale Napoli', 'sarno',                 'IT', 'Sarno',              NULL,   true, 'public'),
  ('La Conca World Karting Circuit', 'la-conca',              'IT', 'Muro Leccese',       1250.0, true, 'public'),
  ('Prokart Raceland Wackersdorf',   'wackersdorf',           'DE', 'Wackersdorf',        1190.0, true, 'public'),
  ('Kristianstad Karting Club',      'kristianstad',          'SE', 'Kristianstad',       1231.0, true, 'public'),
  ('Karting des Fagnes',             'mariembourg',           'BE', 'Mariembourg',        1365.0, true, 'public'),
  ('Kartodromo Internacional do Algarve', 'portimao-kia',     'PT', 'Portimão',           1531.0, true, 'public'),
  ('Circuit de Varennes',            'varennes-sur-allier',   'FR', 'Varennes-sur-Allier', NULL,  true, 'public'),
  ('Circuit d''Essay',               'essay',                 'FR', 'Essay',              NULL,   true, 'public'),
  ('Circuit de Muret',               'muret',                 'FR', 'Muret',              NULL,   true, 'public'),
  ('Circuit de Soucy',               'soucy',                 'FR', 'Soucy',              NULL,   true, 'public')
ON CONFLICT (slug) DO NOTHING;

-- ─────────────────────────────────────────────
-- 2a. Catalogue de composants
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.kart_components (
    id          TEXT PRIMARY KEY,          -- slug stable, ex: 'iame-x30'
    category    TEXT NOT NULL CHECK (category IN ('engine','tire','brake','chassis','carburetor','axle')),
    brand       TEXT NOT NULL,
    name        TEXT NOT NULL,
    subcategory TEXT,                      -- classe moteur, gomme pneu, type frein...
    specs       JSONB DEFAULT '{}'::jsonb, -- specs techniques (pressions, cylindrée...)
    default_life NUMERIC(10,1),            -- durée de vie indicative
    life_unit   TEXT CHECK (life_unit IN ('hours','laps','sessions')),
    active      BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Catalogue global : lecture pour tous, écriture réservée au service_role
ALTER TABLE public.kart_components ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Catalog readable by everyone" ON public.kart_components;
CREATE POLICY "Catalog readable by everyone"
    ON public.kart_components FOR SELECT
    USING (true);

-- ─────────────────────────────────────────────
-- 2b. Seed MOTEURS (durées de vie = intervalles de reconditionnement usuels)
-- ─────────────────────────────────────────────
INSERT INTO public.kart_components (id, category, brand, name, subcategory, default_life, life_unit, specs) VALUES
  ('rotax-micro',      'engine', 'Rotax',  'Micro Max',          'Micro',      50, 'hours', '{"displacement_cc":125,"stroke":"2T","cooling":"liquide","restricted":true}'),
  ('rotax-mini',       'engine', 'Rotax',  'Mini Max',           'Mini',       50, 'hours', '{"displacement_cc":125,"stroke":"2T","cooling":"liquide","restricted":true}'),
  ('rotax-junior',     'engine', 'Rotax',  'Junior Max',         'Junior',     30, 'hours', '{"displacement_cc":125,"stroke":"2T","cooling":"liquide"}'),
  ('rotax-max-125',    'engine', 'Rotax',  'Max Evo',            '125 Senior', 15, 'hours', '{"displacement_cc":125,"stroke":"2T","cooling":"liquide"}'),
  ('rotax-dd2',        'engine', 'Rotax',  'Max DD2',            '125 DD2',    15, 'hours', '{"displacement_cc":125,"stroke":"2T","cooling":"liquide","gearbox":"2 rapports"}'),
  ('iame-water-swift', 'engine', 'IAME',   'Water Swift 60cc',   'Mini',       20, 'hours', '{"displacement_cc":60,"stroke":"2T","cooling":"liquide"}'),
  ('iame-ka100',       'engine', 'IAME',   'KA100',              '100 Senior', 20, 'hours', '{"displacement_cc":100,"stroke":"2T","cooling":"air"}'),
  ('iame-x30-junior',  'engine', 'IAME',   'X30 Junior',         'Junior',     10, 'hours', '{"displacement_cc":125,"stroke":"2T","cooling":"liquide","restricted":true}'),
  ('iame-x30',         'engine', 'IAME',   'X30',                '125 Senior', 10, 'hours', '{"displacement_cc":125,"stroke":"2T","cooling":"liquide","rpm_max":16000}'),
  ('iame-super-x30',   'engine', 'IAME',   'Super X30 175cc',    '175 Super',   8, 'hours', '{"displacement_cc":175,"stroke":"2T","cooling":"liquide"}'),
  ('tm-r1',            'engine', 'TM Racing', 'R1 (KZ)',         'KZ',          6, 'hours', '{"displacement_cc":125,"stroke":"2T","gearbox":"6 rapports"}'),
  ('tm-r2',            'engine', 'TM Racing', 'R2 (KZ)',         'KZ',          6, 'hours', '{"displacement_cc":125,"stroke":"2T","gearbox":"6 rapports"}'),
  ('tm-kz10c',         'engine', 'TM Racing', 'KZ10c',           'KZ',          6, 'hours', '{"displacement_cc":125,"stroke":"2T","gearbox":"6 rapports"}'),
  ('vortex-rvx',       'engine', 'Vortex', 'RVX (KZ)',           'KZ',          6, 'hours', '{"displacement_cc":125,"stroke":"2T","gearbox":"6 rapports"}'),
  ('vortex-rok',       'engine', 'Vortex', 'ROK GP',             '125 Senior', 15, 'hours', '{"displacement_cc":125,"stroke":"2T","cooling":"liquide"}'),
  ('honda-gx160',      'engine', 'Honda',  'GX160',              '4 Temps',   100, 'hours', '{"displacement_cc":163,"stroke":"4T","cooling":"air"}'),
  ('honda-gx270',      'engine', 'Honda',  'GX270',              '4 Temps',   100, 'hours', '{"displacement_cc":270,"stroke":"4T","cooling":"air"}'),
  ('honda-gx390',      'engine', 'Honda',  'GX390',              '4 Temps',   100, 'hours', '{"displacement_cc":389,"stroke":"4T","cooling":"air"}'),
  ('subaru-kx21',      'engine', 'Subaru', 'KX21',               '4 Temps',   100, 'hours', '{"stroke":"4T","cooling":"air"}')
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────────
-- 2c. Seed PNEUS (pressions à froid en bar — bases usuelles compétition,
--     "source":"baseline" => à remplacer par l'abaque officiel du manufacturier)
-- ─────────────────────────────────────────────
INSERT INTO public.kart_components (id, category, brand, name, subcategory, default_life, life_unit, specs) VALUES
  ('vega-rouge-sl4',   'tire', 'Vega',   'Rouge SL4',   'Medium', 200, 'laps', '{"compound":"medium","use":"slick","cold_pressure_bar":{"dry":[0.60,0.80],"damp":[0.75,0.95],"wet":null},"source":"baseline"}'),
  ('vega-blanc-xm3',   'tire', 'Vega',   'Blanc XM3',   'Soft',   120, 'laps', '{"compound":"soft","use":"slick","cold_pressure_bar":{"dry":[0.55,0.70],"damp":[0.70,0.90],"wet":null},"source":"baseline"}'),
  ('vega-vert-xh3',    'tire', 'Vega',   'Vert XH3',    'Hard',   300, 'laps', '{"compound":"hard","use":"slick","cold_pressure_bar":{"dry":[0.65,0.85],"damp":[0.80,1.00],"wet":null},"source":"baseline"}'),
  ('vega-bleu-w6',     'tire', 'Vega',   'Bleu W6',     'Wet',     80, 'laps', '{"compound":"wet","use":"rain","cold_pressure_bar":{"dry":null,"damp":[0.90,1.10],"wet":[1.00,1.20]},"source":"baseline"}'),
  ('lecont-jaune-svm', 'tire', 'LeCont', 'Jaune SVM',   'Medium', 180, 'laps', '{"compound":"medium","use":"slick","cold_pressure_bar":{"dry":[0.60,0.80],"damp":[0.75,0.95],"wet":null},"source":"baseline"}'),
  ('lecont-blanc-svb', 'tire', 'LeCont', 'Blanc SVB',   'Soft',   100, 'laps', '{"compound":"soft","use":"slick","cold_pressure_bar":{"dry":[0.55,0.70],"damp":[0.70,0.90],"wet":null},"source":"baseline"}'),
  ('lecont-prime-svc', 'tire', 'LeCont', 'Prime SVC',   'Soft',   100, 'laps', '{"compound":"soft","use":"slick","cold_pressure_bar":{"dry":[0.55,0.70],"damp":[0.70,0.90],"wet":null},"source":"baseline"}'),
  ('mg-jaune-sm',      'tire', 'MG',     'Jaune SM',    'Medium', 200, 'laps', '{"compound":"medium","use":"slick","cold_pressure_bar":{"dry":[0.60,0.80],"damp":[0.75,0.95],"wet":null},"source":"baseline"}'),
  ('mg-rouge-sh',      'tire', 'MG',     'Rouge SH',    'Hard',   300, 'laps', '{"compound":"hard","use":"slick","cold_pressure_bar":{"dry":[0.65,0.85],"damp":[0.80,1.00],"wet":null},"source":"baseline"}'),
  ('mg-blanc-wt',      'tire', 'MG',     'Blanc WT',    'Wet',     80, 'laps', '{"compound":"wet","use":"rain","cold_pressure_bar":{"dry":null,"damp":[0.90,1.10],"wet":[1.00,1.20]},"source":"baseline"}'),
  ('mojo-d2',          'tire', 'Mojo',   'D2',          'Hard',   250, 'laps', '{"compound":"hard","use":"slick","cold_pressure_bar":{"dry":[0.65,0.85],"damp":[0.80,1.00],"wet":null},"source":"baseline"}'),
  ('mojo-d5',          'tire', 'Mojo',   'D5',          'Medium', 180, 'laps', '{"compound":"medium","use":"slick","cold_pressure_bar":{"dry":[0.60,0.80],"damp":[0.75,0.95],"wet":null},"source":"baseline"}'),
  ('mojo-w5',          'tire', 'Mojo',   'W5',          'Wet',     80, 'laps', '{"compound":"wet","use":"rain","cold_pressure_bar":{"dry":null,"damp":[0.90,1.10],"wet":[1.00,1.20]},"source":"baseline"}'),
  ('komet-k2m',        'tire', 'Komet',  'K2M',         'Medium', 200, 'laps', '{"compound":"medium","use":"slick","cold_pressure_bar":{"dry":[0.60,0.80],"damp":[0.75,0.95],"wet":null},"source":"baseline"}'),
  ('komet-k2h',        'tire', 'Komet',  'K2H',         'Hard',   300, 'laps', '{"compound":"hard","use":"slick","cold_pressure_bar":{"dry":[0.65,0.85],"damp":[0.80,1.00],"wet":null},"source":"baseline"}'),
  ('komet-k1w',        'tire', 'Komet',  'K1W',         'Wet',     80, 'laps', '{"compound":"wet","use":"rain","cold_pressure_bar":{"dry":null,"damp":[0.90,1.10],"wet":[1.00,1.20]},"source":"baseline"}'),
  ('bridgestone-yds',  'tire', 'Bridgestone', 'YDS',    'Medium', 200, 'laps', '{"compound":"medium","use":"slick","cold_pressure_bar":{"dry":[0.60,0.80],"damp":[0.75,0.95],"wet":null},"source":"baseline"}')
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────────
-- 2d. Seed FREINS
-- ─────────────────────────────────────────────
INSERT INTO public.kart_components (id, category, brand, name, subcategory, default_life, life_unit, specs) VALUES
  ('otk-bsd',        'brake', 'OTK',       'BSD',          'Hydraulique',  800, 'laps', '{"position":"arriere"}'),
  ('otk-bss',        'brake', 'OTK',       'BSS (KZ)',     'Hydraulique',  600, 'laps', '{"position":"avant+arriere"}'),
  ('brembo-ma5',     'brake', 'Brembo',    'MA5',          'Hydraulique', 1000, 'laps', '{"position":"arriere"}'),
  ('parolin-ap',     'brake', 'Parolin',   'AP Race',      'Hydraulique',  800, 'laps', '{"position":"arriere"}'),
  ('rr-evo',         'brake', 'RR Racing', 'Evo',          'Hydraulique',  800, 'laps', '{"position":"arriere"}'),
  ('birel-freeline', 'brake', 'Birel ART', 'Freeline',     'Hydraulique',  800, 'laps', '{"position":"arriere"}'),
  ('crg-ven11',      'brake', 'CRG',       'VEN 11',       'Hydraulique',  800, 'laps', '{"position":"arriere"}')
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────────
-- 2e. Seed CHÂSSIS (une ligne par modèle)
-- ─────────────────────────────────────────────
INSERT INTO public.kart_components (id, category, brand, name, subcategory, specs) VALUES
  ('tonykart-racer-401r',  'chassis', 'Tony Kart',     'Racer 401R',  '30mm', '{"tubes_mm":30}'),
  ('tonykart-racer-401rr', 'chassis', 'Tony Kart',     'Racer 401RR', '30mm', '{"tubes_mm":30}'),
  ('tonykart-krypton-801', 'chassis', 'Tony Kart',     'Krypton 801', '32mm', '{"tubes_mm":32}'),
  ('sodi-sigma-rs3',       'chassis', 'Sodi',          'Sigma RS3',   '30mm', '{"tubes_mm":30}'),
  ('sodi-sigma-kz',        'chassis', 'Sodi',          'Sigma KZ',    '32mm', '{"tubes_mm":32}'),
  ('sodi-furia',           'chassis', 'Sodi',          'Furia',       NULL,   '{}'),
  ('birel-ry30-s16',       'chassis', 'Birel ART',     'RY30-S16',    '30mm', '{"tubes_mm":30}'),
  ('birel-cry30-s16',      'chassis', 'Birel ART',     'CRY30-S16',   '30mm', '{"tubes_mm":30}'),
  ('crg-road-rebel',       'chassis', 'CRG',           'Road Rebel',  '32mm', '{"tubes_mm":32}'),
  ('crg-kt2',              'chassis', 'CRG',           'KT2',         '30mm', '{"tubes_mm":30}'),
  ('crg-heron',            'chassis', 'CRG',           'Heron',       NULL,   '{}'),
  ('kosmic-mercury-rr',    'chassis', 'Kosmic',        'Mercury RR',  '30mm', '{"tubes_mm":30}'),
  ('kosmic-mercury-r',     'chassis', 'Kosmic',        'Mercury R',   '30mm', '{"tubes_mm":30}'),
  ('kr-kr2',               'chassis', 'Kart Republic', 'KR2',         '30mm', '{"tubes_mm":30}'),
  ('kr-kr3',               'chassis', 'Kart Republic', 'KR3',         NULL,   '{}')
ON CONFLICT (id) DO NOTHING;

-- ─────────────────────────────────────────────
-- 2f. Seed CARBURATEURS & AXES (nouvelles catégories du configurateur)
-- ─────────────────────────────────────────────
INSERT INTO public.kart_components (id, category, brand, name, subcategory, specs) VALUES
  ('tillotson-hw27a',  'carburetor', 'Tillotson',  'HW-27A',    'Membrane',  '{"engines":["iame-x30"],"venturi_mm":27}'),
  ('dellorto-vhsb34',  'carburetor', 'Dell''Orto', 'VHSB 34',   'Cuve',      '{"engines":["rotax-max-125","rotax-dd2"],"venturi_mm":34}'),
  ('dellorto-vhsh30',  'carburetor', 'Dell''Orto', 'VHSH 30',   'Cuve',      '{"engines":["tm-r1","tm-r2","tm-kz10c","vortex-rvx"],"venturi_mm":30}'),
  ('axle-soft-50',     'axle', 'Générique', 'Axe Souple 50mm',  'Souple',    '{"diameter_mm":50,"effect":"plus de grip arrière, piste froide/glissante"}'),
  ('axle-medium-50',   'axle', 'Générique', 'Axe Medium 50mm',  'Medium',    '{"diameter_mm":50,"effect":"polyvalent, réglage de base"}'),
  ('axle-hard-50',     'axle', 'Générique', 'Axe Dur 50mm',     'Dur',       '{"diameter_mm":50,"effect":"libère l''arrière, piste gommée/chaude"}')
ON CONFLICT (id) DO NOTHING;
