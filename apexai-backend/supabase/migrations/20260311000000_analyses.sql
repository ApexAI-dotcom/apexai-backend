-- =============================================================================
-- Migration: 20260311000000 — table analyses + RLS MVP
-- Description: CREATE TABLE analyses (sessions, télémétrie, insights IA) ; RLS user own data.
-- RLS: SELECT/INSERT WHERE auth.uid() = user_id ; user_id FK → profiles.id.
-- =============================================================================

CREATE TABLE public.analyses (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  track_name VARCHAR(100) NOT NULL,
  session_date DATE,
  telemetry_data JSONB,
  ai_insights JSONB NOT NULL,
  lap_count INTEGER DEFAULT 0 CHECK (lap_count >= 0)
);

ALTER TABLE public.analyses ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own analyses"
  ON public.analyses
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own analyses"
  ON public.analyses
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE INDEX idx_analyses_user_created ON public.analyses (user_id, created_at DESC);
CREATE INDEX idx_analyses_track ON public.analyses (track_name);

COMMENT ON TABLE public.analyses IS 'Analyses de session (piste, télémétrie, insights IA) par utilisateur.';
