-- Apex AI — corrige l'échec d'enregistrement d'une analyse
-- « new row violates row-level security policy (USING expression) for table analyses »
--
-- La politique UPDATE n'avait pas de WITH CHECK. Lors d'un upsert
-- (INSERT ... ON CONFLICT DO UPDATE), Postgres retombe alors sur l'expression
-- USING pour valider la nouvelle ligne, d'où le message ci-dessus.
-- DÉJÀ APPLIQUÉ en prod via MCP — versionné pour traçabilité. Idempotent.

DROP POLICY IF EXISTS "Users update own analyses" ON public.analyses;
CREATE POLICY "Users update own analyses" ON public.analyses
  FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
