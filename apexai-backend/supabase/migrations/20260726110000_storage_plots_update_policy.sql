-- Apex AI — corrige la perte des graphiques d'analyse
-- « new row violates row-level security policy » sur analysis-plots
--
-- Les graphiques sont envoyés avec upsert:true. Quand le fichier existe déjà,
-- Supabase Storage effectue un UPDATE sur storage.objects ; sans politique
-- UPDATE, l'envoi échouait et le pilote perdait tous ses graphiques.
-- DÉJÀ APPLIQUÉ en prod via MCP — versionné pour traçabilité. Idempotent.

DROP POLICY IF EXISTS "Users update own plots" ON storage.objects;
CREATE POLICY "Users update own plots" ON storage.objects
  FOR UPDATE
  USING (bucket_id = 'analysis-plots' AND (storage.foldername(name))[1] = (auth.uid())::text)
  WITH CHECK (bucket_id = 'analysis-plots' AND (storage.foldername(name))[1] = (auth.uid())::text);
