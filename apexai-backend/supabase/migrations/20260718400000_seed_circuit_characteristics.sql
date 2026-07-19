-- Apex AI — Migration: caractéristiques des circuits officiels
-- Les fiches officielles arrivent pré-remplies : la télémétrie n'est qu'un
-- complément (circuits non répertoriés / affinage).
-- Codes numériques : speed_ratio 0=sinueux 1=mixte 2=rapide
--                    rotation    0=horaire 1=anti-horaire
--                    elevation   0=plat    1=vallonné
--                    bumpiness   0=lisse   1=bosselé
-- Sources : Adria = mesuré sur télémétrie réelle (session AiM 11 tours) ;
--           autres = caractérisation publique de notoriété, à affiner.

-- Adria (MESURÉ : 11 virages, 0 épingle, 5 rapides, apex moyen 80 km/h, horaire)
UPDATE public.circuits SET speed_ratio=2, rotation=0, hairpins_count=0, fast_corners_count=5, elevation=0, bumpiness=0, corners_count=11 WHERE slug='adria-karting-raceway';

-- Circuits rapides et fluides
UPDATE public.circuits SET speed_ratio=2, rotation=0, hairpins_count=2, fast_corners_count=4, elevation=0, bumpiness=0 WHERE slug='south-garda-karting';
UPDATE public.circuits SET speed_ratio=2, rotation=0, hairpins_count=2, fast_corners_count=5, elevation=0, bumpiness=0 WHERE slug='pf-international';
UPDATE public.circuits SET speed_ratio=2, rotation=0, hairpins_count=2, fast_corners_count=5, elevation=0, bumpiness=0 WHERE slug='zuera';
UPDATE public.circuits SET speed_ratio=2, rotation=0, hairpins_count=2, fast_corners_count=5, elevation=0, bumpiness=0 WHERE slug='sarno';
UPDATE public.circuits SET speed_ratio=2, rotation=0, hairpins_count=2, fast_corners_count=4, elevation=0, bumpiness=0 WHERE slug='kristianstad';
UPDATE public.circuits SET speed_ratio=2, rotation=0, hairpins_count=2, fast_corners_count=4, elevation=0, bumpiness=0 WHERE slug='mariembourg';

-- Circuits mixtes / techniques
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=4, elevation=0, bumpiness=0 WHERE slug='karting-genk';
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=3, elevation=0, bumpiness=0 WHERE slug='le-mans-karting';
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=2, elevation=0, bumpiness=0 WHERE slug='angerville';
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=3, elevation=0, bumpiness=0 WHERE slug='salbris';
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=4, elevation=0, bumpiness=0 WHERE slug='la-conca';
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=3, elevation=0, bumpiness=0 WHERE slug='wackersdorf';
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=3, elevation=1, bumpiness=0 WHERE slug='portimao-kia';

-- Circuits français régionaux
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=3, elevation=0, bumpiness=0 WHERE slug='essay';
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=3, elevation=0, bumpiness=0 WHERE slug='muret';
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=3, elevation=0, bumpiness=0 WHERE slug='soucy';
UPDATE public.circuits SET speed_ratio=1, rotation=0, hairpins_count=3, fast_corners_count=3, elevation=0, bumpiness=0 WHERE slug='varennes-sur-allier';

-- Marquage de la source des caractéristiques
UPDATE public.circuits SET source='public+mesure' WHERE slug='adria-karting-raceway';

-- Ménage des circuits de test (créés pendant le debug)
DELETE FROM public.circuits WHERE slug IN ('adru', 'nouveau-circuit');
