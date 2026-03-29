-- Migration script to add 'driving_profile' and 'entry_type' to kart tables

-- 1. Add driving_profile to kart_profiles
ALTER TABLE public.kart_profiles 
ADD COLUMN IF NOT EXISTS driving_profile TEXT DEFAULT 'balanced' CHECK (driving_profile IN ('longevity', 'performance', 'balanced', 'leisure'));

-- 2. Add entry_type to kart_component_history
ALTER TABLE public.kart_component_history 
ADD COLUMN IF NOT EXISTS entry_type TEXT DEFAULT 'reset' CHECK (entry_type IN ('reset', 'manual'));
