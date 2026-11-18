-- ============================================================================
-- Espace Team (écoles, clubs, coachs) — étape E0 : le socle sécurisé
-- ----------------------------------------------------------------------------
-- Tout est AJOUTÉ : aucune table existante n'est renommée ni vidée.
-- Retour arrière : 20261118010000_team_space.down.sql
--
-- Principe de sécurité
--   - Le coach LIT les séances de ses pilotes par la RLS (fonctions ci-dessous).
--   - Personne n'ÉCRIT directement dans ces tables depuis l'app : tout passe
--     par l'API (clé de service), qui vérifie les droits. D'où : aucune
--     politique INSERT / UPDATE / DELETE sur les nouvelles tables.
--   - Interrupteur : public.app_flags('team_space'). Coupé (défaut), aucun
--     coach ne voit rien, quelles que soient les lignes présentes.
-- ============================================================================

-- ── Interrupteur ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.app_flags (
    key        TEXT PRIMARY KEY,
    enabled    BOOLEAN NOT NULL DEFAULT false,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.app_flags ENABLE ROW LEVEL SECURITY;
INSERT INTO public.app_flags (key, enabled) VALUES ('team_space', false)
ON CONFLICT (key) DO NOTHING;

-- ── Demandes « Contactez-nous » (offre Team sur devis) ──────────────────────
CREATE TABLE IF NOT EXISTS public.contact_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 120),
    email           TEXT NOT NULL CHECK (char_length(email) BETWEEN 3 AND 254),
    phone           TEXT CHECK (phone IS NULL OR char_length(phone) <= 40),
    structure_name  TEXT CHECK (structure_name IS NULL OR char_length(structure_name) <= 160),
    kind            TEXT NOT NULL DEFAULT 'ecole' CHECK (kind IN ('ecole','club','coach','autre')),
    pilots_estimate TEXT CHECK (pilots_estimate IS NULL OR char_length(pilots_estimate) <= 40),
    message         TEXT CHECK (message IS NULL OR char_length(message) <= 4000),
    user_id         UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    status          TEXT NOT NULL DEFAULT 'nouvelle' CHECK (status IN ('nouvelle','en_discussion','signee','sans_suite')),
    admin_note      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.contact_requests ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_contact_requests_created ON public.contact_requests (created_at DESC);

-- ── Structures ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.structures (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name               TEXT NOT NULL CHECK (char_length(name) BETWEEN 1 AND 160),
    kind               TEXT NOT NULL DEFAULT 'ecole' CHECK (kind IN ('ecole','club','coach')),
    status             TEXT NOT NULL DEFAULT 'essai' CHECK (status IN ('essai','active','suspendue','terminee')),
    trial_until        TIMESTAMPTZ,
    contract_until     TIMESTAMPTZ,
    max_pilots         INTEGER CHECK (max_pilots IS NULL OR max_pilots > 0),
    max_coaches        INTEGER CHECK (max_coaches IS NULL OR max_coaches > 0),
    max_karts          INTEGER CHECK (max_karts IS NULL OR max_karts > 0),
    contact_request_id UUID REFERENCES public.contact_requests(id) ON DELETE SET NULL,
    notes_admin        TEXT,
    created_by         UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.structures ENABLE ROW LEVEL SECURITY;

-- ── Membres (coachs et pilotes) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.structure_members (
    structure_id          UUID NOT NULL REFERENCES public.structures(id) ON DELETE CASCADE,
    user_id               UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role                  TEXT NOT NULL CHECK (role IN ('coach','pilote')),
    status                TEXT NOT NULL DEFAULT 'actif' CHECK (status IN ('actif','parti','retire')),
    consent_at            TIMESTAMPTZ,          -- accord explicite du pilote
    consent_version       TEXT,
    guardian_certified_by UUID REFERENCES auth.users(id) ON DELETE SET NULL, -- mineur : l'école certifie l'accord parental
    guardian_certified_at TIMESTAMPTZ,
    joined_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    left_at               TIMESTAMPTZ,
    PRIMARY KEY (structure_id, user_id),
    -- Un pilote actif a forcément donné son accord.
    CONSTRAINT pilot_needs_consent CHECK (role <> 'pilote' OR status <> 'actif' OR consent_at IS NOT NULL)
);
ALTER TABLE public.structure_members ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_structure_members_user ON public.structure_members (user_id, status);
CREATE INDEX IF NOT EXISTS idx_structure_members_struct ON public.structure_members (structure_id, role, status);

-- ── Invitations (lien ou code, QR imprimable) ───────────────────────────────
CREATE TABLE IF NOT EXISTS public.structure_invites (
    code         TEXT PRIMARY KEY CHECK (code ~ '^[A-Z0-9]{6,32}$'),
    structure_id UUID NOT NULL REFERENCES public.structures(id) ON DELETE CASCADE,
    role         TEXT NOT NULL CHECK (role IN ('coach','pilote')),
    email        TEXT,                -- invitation nominative (coach), sinon NULL
    created_by   UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    expires_at   TIMESTAMPTZ,
    max_uses     INTEGER CHECK (max_uses IS NULL OR max_uses > 0),
    uses         INTEGER NOT NULL DEFAULT 0,
    revoked      BOOLEAN NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.structure_invites ENABLE ROW LEVEL SECURITY;

-- ── Anciennes séances partagées volontairement par le pilote ────────────────
CREATE TABLE IF NOT EXISTS public.shared_analyses (
    structure_id UUID NOT NULL REFERENCES public.structures(id) ON DELETE CASCADE,
    analysis_id  TEXT NOT NULL REFERENCES public.analyses(id) ON DELETE CASCADE,
    pilot_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    shared_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (structure_id, analysis_id)
);
ALTER TABLE public.shared_analyses ENABLE ROW LEVEL SECURITY;

-- ── Notes et objectifs du coach ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.coach_notes (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    structure_id  UUID NOT NULL REFERENCES public.structures(id) ON DELETE CASCADE,
    pilot_id      UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    author_id     UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    analysis_id   TEXT REFERENCES public.analyses(id) ON DELETE CASCADE,  -- NULL = objectif général
    kind          TEXT NOT NULL DEFAULT 'note' CHECK (kind IN ('note','objectif')),
    corner_number INTEGER,
    body          TEXT NOT NULL CHECK (char_length(body) BETWEEN 1 AND 2000),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at       TIMESTAMPTZ,
    done_at       TIMESTAMPTZ
);
ALTER TABLE public.coach_notes ENABLE ROW LEVEL SECURITY;
CREATE INDEX IF NOT EXISTS idx_coach_notes_pilot ON public.coach_notes (pilot_id, created_at DESC);

-- ── Séance déposée par un coach au nom du pilote ────────────────────────────
ALTER TABLE public.analyses ADD COLUMN IF NOT EXISTS uploaded_by UUID REFERENCES auth.users(id) ON DELETE SET NULL;

-- ============================================================================
-- Fonctions de droit (SECURITY DEFINER : lisent les tables de membres sans
-- dépendre de leurs propres politiques ; search_path figé).
-- ============================================================================
CREATE OR REPLACE FUNCTION public.team_space_enabled()
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT COALESCE((SELECT enabled FROM public.app_flags WHERE key = 'team_space'), false);
$$;

-- Une structure « vivante » : en essai non expiré, ou active et sous contrat.
CREATE OR REPLACE FUNCTION public.structure_is_live(p_structure UUID)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.structures s
        WHERE s.id = p_structure
          AND (
                (s.status = 'essai'  AND s.trial_until IS NOT NULL AND s.trial_until > now())
             OR (s.status = 'active' AND (s.contract_until IS NULL OR s.contract_until > now()))
          )
    );
$$;

-- L'utilisateur connecté est-il coach actif d'une structure vivante où ce pilote est membre actif ?
CREATE OR REPLACE FUNCTION public.is_coach_of(p_pilot UUID)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT public.team_space_enabled()
       AND auth.uid() IS NOT NULL
       AND p_pilot IS NOT NULL
       AND p_pilot <> auth.uid()
       AND EXISTS (
            SELECT 1
            FROM public.structure_members c
            JOIN public.structure_members p
              ON p.structure_id = c.structure_id
            WHERE c.user_id = auth.uid() AND c.role = 'coach'  AND c.status = 'actif'
              AND p.user_id = p_pilot    AND p.role = 'pilote' AND p.status = 'actif'
              AND public.structure_is_live(c.structure_id)
       );
$$;

-- Le coach connecté peut-il voir CETTE séance ? Séances déposées depuis
-- l'arrivée du pilote dans la structure, ou partagées par lui.
CREATE OR REPLACE FUNCTION public.coach_can_view_analysis(p_owner UUID, p_analysis TEXT, p_created TIMESTAMPTZ)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT public.team_space_enabled()
       AND auth.uid() IS NOT NULL
       AND p_owner IS NOT NULL
       AND p_owner <> auth.uid()
       AND EXISTS (
            SELECT 1
            FROM public.structure_members c
            JOIN public.structure_members p
              ON p.structure_id = c.structure_id
            WHERE c.user_id = auth.uid() AND c.role = 'coach'  AND c.status = 'actif'
              AND p.user_id = p_owner    AND p.role = 'pilote' AND p.status = 'actif'
              AND public.structure_is_live(c.structure_id)
              AND (
                    p_created >= p.joined_at
                 OR EXISTS (SELECT 1 FROM public.shared_analyses sa
                            WHERE sa.structure_id = c.structure_id
                              AND sa.analysis_id = p_analysis
                              AND sa.pilot_id = p_owner)
              )
       );
$$;

-- L'utilisateur connecté est-il coach actif de cette structure ?
CREATE OR REPLACE FUNCTION public.is_coach_in(p_structure UUID)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT public.team_space_enabled()
       AND EXISTS (SELECT 1 FROM public.structure_members m
                   WHERE m.structure_id = p_structure AND m.user_id = auth.uid()
                     AND m.role = 'coach' AND m.status = 'actif')
       AND public.structure_is_live(p_structure);
$$;

REVOKE ALL ON FUNCTION public.team_space_enabled() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.structure_is_live(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.is_coach_of(UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.coach_can_view_analysis(UUID, TEXT, TIMESTAMPTZ) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.is_coach_in(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.team_space_enabled() TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.structure_is_live(UUID) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.is_coach_of(UUID) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.coach_can_view_analysis(UUID, TEXT, TIMESTAMPTZ) TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.is_coach_in(UUID) TO authenticated, service_role;

-- ============================================================================
-- Politiques de LECTURE (aucune politique d'écriture : l'API écrit)
-- ============================================================================
-- Séances : le coach voit celles de ses pilotes (règles ci-dessus).
DROP POLICY IF EXISTS "Coach voit les séances de ses pilotes" ON public.analyses;
CREATE POLICY "Coach voit les séances de ses pilotes"
    ON public.analyses FOR SELECT TO authenticated
    USING (public.coach_can_view_analysis(user_id, id, created_at));

-- Structures : visibles par leurs membres actifs.
DROP POLICY IF EXISTS "Membres voient leur structure" ON public.structures;
CREATE POLICY "Membres voient leur structure"
    ON public.structures FOR SELECT TO authenticated
    USING (public.team_space_enabled() AND EXISTS (
        SELECT 1 FROM public.structure_members m
        WHERE m.structure_id = structures.id AND m.user_id = auth.uid() AND m.status = 'actif'));

-- Membres : chacun voit ses propres adhésions ; un coach voit les membres
-- actifs de sa structure.
DROP POLICY IF EXISTS "Voir ses adhésions" ON public.structure_members;
CREATE POLICY "Voir ses adhésions"
    ON public.structure_members FOR SELECT TO authenticated
    USING (user_id = auth.uid());
DROP POLICY IF EXISTS "Coach voit son équipe" ON public.structure_members;
CREATE POLICY "Coach voit son équipe"
    ON public.structure_members FOR SELECT TO authenticated
    USING (status = 'actif' AND public.is_coach_in(structure_id));

-- Partages : le pilote voit les siens ; le coach ceux de ses pilotes.
DROP POLICY IF EXISTS "Voir ses partages" ON public.shared_analyses;
CREATE POLICY "Voir ses partages"
    ON public.shared_analyses FOR SELECT TO authenticated
    USING (pilot_id = auth.uid() OR (public.is_coach_in(structure_id) AND public.is_coach_of(pilot_id)));

-- Notes : le pilote voit les notes qui lui sont adressées (même après son
-- départ : elles sont à lui) ; le coach celles de sa structure pour ses
-- pilotes encore membres.
DROP POLICY IF EXISTS "Pilote voit ses notes" ON public.coach_notes;
CREATE POLICY "Pilote voit ses notes"
    ON public.coach_notes FOR SELECT TO authenticated
    USING (pilot_id = auth.uid());
DROP POLICY IF EXISTS "Coach voit les notes de son équipe" ON public.coach_notes;
CREATE POLICY "Coach voit les notes de son équipe"
    ON public.coach_notes FOR SELECT TO authenticated
    USING (public.is_coach_in(structure_id) AND public.is_coach_of(pilot_id));

-- app_flags, contact_requests, structure_invites : aucune politique =
-- inaccessibles depuis l'app, réservées à l'API (clé de service).
