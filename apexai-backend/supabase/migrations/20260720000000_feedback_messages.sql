-- Apex AI — Sprint 3 : Boîte à recommandations
-- Canal de feedback PRIVÉ entre un pilote et l'admin : idées d'amélioration,
-- bugs du terrain, questions. Les échanges ne sont visibles que par leur
-- auteur (RLS) et par l'admin (backend service_role).
-- DÉJÀ APPLIQUÉ en prod via MCP — versionné pour traçabilité. Idempotent.

CREATE TABLE IF NOT EXISTS public.feedback_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    category    TEXT NOT NULL DEFAULT 'idea' CHECK (category IN ('idea','bug','question','other')),
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','read','in_progress','done','archived')),
    admin_reply TEXT,
    replied_at  TIMESTAMPTZ,
    context     JSONB,           -- page d'origine, version app... (diagnostic)
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_user ON public.feedback_messages (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON public.feedback_messages (status, created_at DESC);

ALTER TABLE public.feedback_messages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users manage their own feedback" ON public.feedback_messages;
CREATE POLICY "Users manage their own feedback"
    ON public.feedback_messages FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

DROP TRIGGER IF EXISTS update_feedback_modtime ON public.feedback_messages;
CREATE TRIGGER update_feedback_modtime
BEFORE UPDATE ON public.feedback_messages
FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
