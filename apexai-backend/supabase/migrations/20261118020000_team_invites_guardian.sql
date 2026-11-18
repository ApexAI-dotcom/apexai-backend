-- Espace Team, étape E2 : un code pilote peut porter la certification de
-- l'accord parental (pilotes mineurs : l'école certifie, case du coach).
-- Retour arrière : 20261118020000_team_invites_guardian.down.sql
ALTER TABLE public.structure_invites ADD COLUMN IF NOT EXISTS guardian_certified BOOLEAN NOT NULL DEFAULT false;
