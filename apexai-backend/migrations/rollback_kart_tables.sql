-- Rollback script for Mon Kart Tables

-- Drop tables and associated constraints, indexes, triggers
DROP TRIGGER IF EXISTS update_kart_profiles_modtime ON public.kart_profiles;

DROP TABLE IF EXISTS public.kart_component_history CASCADE;
DROP TABLE IF EXISTS public.kart_session_logs CASCADE;
DROP TABLE IF EXISTS public.kart_profiles CASCADE;

-- (Optional) If you created the trigger function specifically for this and it's not used elsewhere:
-- DROP FUNCTION IF EXISTS update_modified_column() CASCADE;
-- Keeping the function is safer if other tables might use it.
