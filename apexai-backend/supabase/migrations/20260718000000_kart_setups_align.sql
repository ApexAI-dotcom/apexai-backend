-- Apex AI — Migration: aligne la table kart_setups (et complète circuits) avec le code backend
-- Contexte : kart_setups / circuits avaient été créées manuellement, incomplètes.
--            Cette migration ajoute toutes les colonnes attendues par save_kart_setup().
-- Idempotent : ADD COLUMN IF NOT EXISTS => rejouable sans risque.
-- À exécuter dans Supabase → SQL Editor (ou via connexion Postgres directe).

-- ─────────────────────────────────────────────
-- 1. kart_setups : colonnes manquantes
-- ─────────────────────────────────────────────

-- Contexte session
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS setup_name         TEXT;
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS air_temp           NUMERIC(6, 2);
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS track_temp         NUMERIC(6, 2);
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS mode               TEXT;

-- Pneus
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS tire_model         TEXT;
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS cold_pressure_front NUMERIC(6, 3);
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS cold_pressure_rear  NUMERIC(6, 3);
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS hot_pressure_front  NUMERIC(6, 3);
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS hot_pressure_rear   NUMERIC(6, 3);

-- Châssis
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS track_width_front  NUMERIC(7, 2);
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS track_width_rear   NUMERIC(7, 2);
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS ride_height_front  TEXT;
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS ride_height_rear   TEXT;
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS camber             TEXT;
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS caster             TEXT;
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS rear_axle          TEXT;

-- Transmission
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS sprocket_front     INTEGER;
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS sprocket_rear      INTEGER;

-- Poids
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS driver_weight      NUMERIC(6, 2);
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS kart_weight        NUMERIC(6, 2);
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS target_weight      NUMERIC(6, 2);
ALTER TABLE public.kart_setups ADD COLUMN IF NOT EXISTS ballast            NUMERIC(6, 2);

-- ─────────────────────────────────────────────
-- 2. circuits : colonnes de traçabilité (complétude du schéma)
--    Le code les prévoit déjà ; on les matérialise pour cohérence.
-- ─────────────────────────────────────────────
ALTER TABLE public.circuits ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES auth.users(id) ON DELETE SET NULL;
ALTER TABLE public.circuits ADD COLUMN IF NOT EXISTS verified   BOOLEAN DEFAULT false;
