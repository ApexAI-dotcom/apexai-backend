-- =============================================================================
-- Migration: table profiles + RLS + trigger sur auth.users
-- À exécuter dans Supabase SQL Editor (ou via Supabase CLI)
-- =============================================================================

-- 1. Table profiles (référence auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
  id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email      TEXT,
  full_name  TEXT,
  avatar_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index optionnel pour recherches par email
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles(email);

-- 2. Activer Row Level Security (RLS)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- 3. Policy : les utilisateurs voient uniquement leur propre profil
CREATE POLICY "Users can view own profile"
  ON public.profiles
  FOR SELECT
  USING (auth.uid() = id);

-- Les utilisateurs peuvent mettre à jour leur propre profil (optionnel, utile pour full_name / avatar_url)
CREATE POLICY "Users can update own profile"
  ON public.profiles
  FOR UPDATE
  USING (auth.uid() = id)
  WITH CHECK (auth.uid() = id);

-- 4. Trigger : insérer une ligne dans profiles à chaque nouvel utilisateur auth.users
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, avatar_url, created_at, updated_at)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', ''),
    NEW.raw_user_meta_data->>'avatar_url',
    now(),
    now()
  )
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

-- Lier le trigger à auth.users (événement AFTER INSERT)
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

-- 5. (Optionnel) Remplir les profils existants qui n'ont pas encore de ligne
INSERT INTO public.profiles (id, email, full_name, avatar_url, created_at, updated_at)
SELECT
  id,
  email,
  COALESCE(raw_user_meta_data->>'full_name', raw_user_meta_data->>'name', ''),
  raw_user_meta_data->>'avatar_url',
  created_at,
  updated_at
FROM auth.users
ON CONFLICT (id) DO NOTHING;

-- Commentaire sur la table
COMMENT ON TABLE public.profiles IS 'Profils utilisateurs (synchro avec auth.users via trigger).';
