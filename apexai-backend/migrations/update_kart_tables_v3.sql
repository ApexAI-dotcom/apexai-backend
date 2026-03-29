-- Migration script to add 'saved_setups' to kart_profiles

ALTER TABLE public.kart_profiles 
ADD COLUMN IF NOT EXISTS saved_setups JSONB DEFAULT '[]'::jsonb;
