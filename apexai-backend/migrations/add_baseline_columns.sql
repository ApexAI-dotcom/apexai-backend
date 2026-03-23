-- Apex AI — Migration: Add baseline columns to profiles table
-- Run via Supabase SQL Editor or admin migration endpoint
-- Safe: IF NOT EXISTS prevents errors on re-run

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS baseline_score real;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS baseline_time real;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS objectives_reset_at timestamptz;

-- Optional: comment columns for clarity
COMMENT ON COLUMN profiles.baseline_score IS 'Score de référence pour calcul de progression homepage (set on reset)';
COMMENT ON COLUMN profiles.baseline_time IS 'Temps de référence pour calcul de progression homepage (set on reset)';
COMMENT ON COLUMN profiles.objectives_reset_at IS 'Date de dernière réinitialisation des objectifs homepage';
