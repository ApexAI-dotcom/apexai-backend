-- Migration script to add Mon Kart tables
-- Created for the Mon Kart MVP

-- 1. kart_profiles table
CREATE TABLE IF NOT EXISTS public.kart_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    mon_kart_enabled BOOLEAN DEFAULT false,
    
    -- Engine
    engine_model TEXT,
    engine_preset TEXT,
    engine_hours_current NUMERIC(10, 2) DEFAULT 0.0,
    engine_hours_life NUMERIC(10, 2) DEFAULT 15.0,
    engine_sessions NUMERIC(10, 2) DEFAULT 0.0,
    
    -- Tires
    tires_model TEXT,
    tires_preset TEXT,
    tires_sessions_current INTEGER DEFAULT 0,
    tires_sessions_life INTEGER DEFAULT 50,
    
    -- Brakes
    brakes_model TEXT,
    brakes_preset TEXT,
    brakes_sessions_current INTEGER DEFAULT 0,
    brakes_sessions_life INTEGER DEFAULT 100,
    
    -- Battery
    battery_voltage_last NUMERIC(5, 2),
    battery_voltage_min_ever NUMERIC(5, 2),
    
    -- Setup
    setup_json JSONB DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. kart_session_logs table
CREATE TABLE IF NOT EXISTS public.kart_session_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- Unique file signature to avoid duplication
    file_signature TEXT NOT NULL,
    
    -- Where it came from
    imported_via TEXT NOT NULL CHECK (imported_via IN ('analyze', 'bulk_import')),
    analysis_id TEXT REFERENCES public.analyses(id) ON DELETE SET NULL,
    
    -- Session metadata
    session_date TIMESTAMP WITH TIME ZONE,
    circuit_name TEXT,
    driver_name TEXT,
    
    -- Aggregates
    duration_seconds NUMERIC(10, 2) DEFAULT 0.0,
    duration_hours NUMERIC(10, 2) DEFAULT 0.0,
    laps_count INTEGER DEFAULT 0,
    best_lap_time NUMERIC(10, 3),
    
    -- Mechanical aggregates
    rpm_max NUMERIC(10, 2),
    rpm_avg NUMERIC(10, 2),
    water_temp_max NUMERIC(10, 2),
    water_temp_avg NUMERIC(10, 2),
    exhaust_temp_max NUMERIC(10, 2),
    exhaust_temp_avg NUMERIC(10, 2),
    speed_max_kmh NUMERIC(10, 2),
    g_lateral_max NUMERIC(10, 2),
    g_braking_max NUMERIC(10, 2),
    battery_voltage_avg NUMERIC(5, 2),
    battery_voltage_min NUMERIC(5, 2),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add unique constraint on user_id and file_signature
CREATE UNIQUE INDEX idx_kart_session_logs_unique_sig ON public.kart_session_logs (user_id, file_signature);
ALTER TABLE public.kart_session_logs ADD CONSTRAINT unique_user_file_signature UNIQUE USING INDEX idx_kart_session_logs_unique_sig;

-- 3. kart_component_history table
CREATE TABLE IF NOT EXISTS public.kart_component_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    component_type TEXT NOT NULL CHECK (component_type IN ('engine', 'tires', 'brakes')),
    
    reset_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Values at the time of reset
    previous_hours NUMERIC(10, 2),
    previous_sessions INTEGER,
    
    notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- RLS Policies
ALTER TABLE public.kart_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.kart_session_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.kart_component_history ENABLE ROW LEVEL SECURITY;

-- Create policies (assuming standard auth.uid() checks)
CREATE POLICY "Users can manage their own kart profile"
    ON public.kart_profiles
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can manage their own kart sessions"
    ON public.kart_session_logs
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can manage their own kart history"
    ON public.kart_component_history
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Optional: Triggers to maintain updated_at on kart_profiles
CREATE OR REPLACE FUNCTION update_modified_column() 
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW; 
END;
$$ language 'plpgsql';

CREATE TRIGGER update_kart_profiles_modtime 
BEFORE UPDATE ON public.kart_profiles
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
