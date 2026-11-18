-- Retour arrière de 20261118010000_team_space.sql (espace Team, E0).
-- Retire l'accès coach et les tables ajoutées. Les séances des pilotes ne
-- sont pas touchées (seule la colonne uploaded_by, ajoutée par l'étape,
-- disparaît).
-- Interrupteur plus doux, sans rien supprimer :
--   UPDATE public.app_flags SET enabled = false WHERE key = 'team_space';

DROP POLICY IF EXISTS "Coach voit les séances de ses pilotes" ON public.analyses;
DROP POLICY IF EXISTS "Membres voient leur structure" ON public.structures;

DROP TABLE IF EXISTS public.coach_notes;
DROP TABLE IF EXISTS public.shared_analyses;
DROP TABLE IF EXISTS public.structure_invites;
DROP TABLE IF EXISTS public.structure_members;
DROP TABLE IF EXISTS public.structures;
DROP TABLE IF EXISTS public.contact_requests;

DROP FUNCTION IF EXISTS public.is_coach_in(UUID);
DROP FUNCTION IF EXISTS public.coach_can_view_analysis(UUID, TEXT, TIMESTAMPTZ);
DROP FUNCTION IF EXISTS public.is_coach_of(UUID);
DROP FUNCTION IF EXISTS public.structure_is_live(UUID);
DROP FUNCTION IF EXISTS public.team_space_enabled();

ALTER TABLE public.analyses DROP COLUMN IF EXISTS uploaded_by;
DELETE FROM public.app_flags WHERE key = 'team_space';
-- app_flags est gardée (vide) : d'autres interrupteurs pourront s'y ajouter.
