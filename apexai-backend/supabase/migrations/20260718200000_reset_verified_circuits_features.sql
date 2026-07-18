-- Apex AI — Migration: purge des caractéristiques des circuits officiels
-- Contexte : avant la protection des circuits verified, des sauvegardes UI ont pu
--            écrire les valeurs génériques par défaut (mixte/horaire/plat/lisse/2/3)
--            dans les fiches officielles seedées. On remet ces champs à NULL :
--            l'enrichissement automatique par télémétrie (create_circuit) les
--            remplira avec des données mesurées réelles.
-- NB : ne touche ni au nom, ni au slug, ni à la longueur, ni au pays (données publiques).

UPDATE public.circuits
SET speed_ratio        = NULL,
    rotation           = NULL,
    hairpins_count     = NULL,
    fast_corners_count = NULL,
    elevation          = NULL,
    bumpiness          = NULL
WHERE verified = true;
