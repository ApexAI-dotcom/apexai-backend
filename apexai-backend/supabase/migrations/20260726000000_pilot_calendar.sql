-- Apex AI — Phase 2 : calendrier du pilote (vie sportive)
-- Courses, entraînements, sessions de coaching, échéances d'inscription.
-- Calendrier PERSONNEL : chaque pilote ne voit et ne gère que ses propres
-- échéances. Le partage (coach / équipe) pourra s'ajouter plus tard sans
-- migration destructive, via une colonne d'appartenance.
-- Idempotent.

CREATE TABLE IF NOT EXISTS public.pilot_events (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    title         TEXT NOT NULL,
    -- race     : course / compétition
    -- training : entraînement libre
    -- coaching : séance avec un coach
    -- deadline : échéance administrative (inscription, licence, paiement)
    -- other    : divers
    event_type    TEXT NOT NULL DEFAULT 'training'
                  CHECK (event_type IN ('race','training','coaching','deadline','other')),

    -- Date/heure de début. `all_day` évite d'inventer une heure quand le pilote
    -- ne connaît que le jour (typique d'une échéance d'inscription).
    starts_at     TIMESTAMPTZ NOT NULL,
    ends_at       TIMESTAMPTZ,
    all_day       BOOLEAN NOT NULL DEFAULT FALSE,

    circuit_name  TEXT,
    location      TEXT,
    notes         TEXT,

    -- Permet au pilote de cocher ce qui est fait sans perdre l'historique.
    completed     BOOLEAN NOT NULL DEFAULT FALSE,

    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT pilot_events_title_not_blank CHECK (length(btrim(title)) > 0),
    CONSTRAINT pilot_events_end_after_start CHECK (ends_at IS NULL OR ends_at >= starts_at)
);

-- Requête dominante : « mes événements, du plus proche au plus lointain ».
CREATE INDEX IF NOT EXISTS idx_pilot_events_user_start
    ON public.pilot_events (user_id, starts_at);

ALTER TABLE public.pilot_events ENABLE ROW LEVEL SECURITY;

-- Le backend écrit via service_role. Ces policies protègent en plus l'accès
-- direct : un pilote ne peut voir et modifier que ses propres échéances.
DROP POLICY IF EXISTS pilot_events_select_own ON public.pilot_events;
CREATE POLICY pilot_events_select_own ON public.pilot_events
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS pilot_events_insert_own ON public.pilot_events;
CREATE POLICY pilot_events_insert_own ON public.pilot_events
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS pilot_events_update_own ON public.pilot_events;
CREATE POLICY pilot_events_update_own ON public.pilot_events
    FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS pilot_events_delete_own ON public.pilot_events;
CREATE POLICY pilot_events_delete_own ON public.pilot_events
    FOR DELETE USING (auth.uid() = user_id);

DROP TRIGGER IF EXISTS update_pilot_events_modtime ON public.pilot_events;
CREATE TRIGGER update_pilot_events_modtime
BEFORE UPDATE ON public.pilot_events
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
