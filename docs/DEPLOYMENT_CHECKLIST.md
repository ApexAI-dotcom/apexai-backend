# Checklist de déploiement – Abonnements Apex AI

À valider avant et après la mise en production du système d’abonnements Stripe.

---

## Pré-déploiement

- [ ] **Variables d’environnement configurées en production (ex. Railway)**  
  - `STRIPE_SECRET_KEY` (clé live `sk_live_*`, pas de clé test en prod)
  - `STRIPE_WEBHOOK_SECRET` (secret du webhook **de production**)
  - `SUPABASE_URL` et `SUPABASE_SERVICE_KEY` (projet Supabase de prod)
  - `FRONTEND_URL` (URL du frontend de prod pour success/cancel_url)

- [ ] **Migration Supabase exécutée en production**  
  - Fichier : `apexai-backend/supabase/migrations/20260102000000_add_profiles_subscription_and_usage_logs.sql`
  - Vérifier : colonnes abonnement sur `profiles`, trigger `protect_profiles_subscription_columns`, table `usage_logs` et politiques RLS

- [ ] **Price IDs Stripe de production configurés**  
  - Remplacer les price IDs de test par les IDs live (`price_*` du tableau de bord Stripe)
  - Mapping : `racer_monthly`, `racer_annual`, `team_monthly`, `team_annual`

- [ ] **Webhook Stripe configuré avec l’URL de prod**  
  - URL : `https://<votre-backend>/api/stripe/webhook`
  - Événements à activer : `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
  - Récupérer le **Signing secret** (whsec_*) et le mettre dans `STRIPE_WEBHOOK_SECRET`

- [ ] **Aucune clé secrète en dur dans le code**  
  - Vérifier qu’il n’y a pas de fallback `os.getenv("STRIPE_*", "sk_...")` ou `"whsec_..."` en production

---

## Tests avant mise en ligne

- [ ] **Test paiement réel (ou test mode avec carte 4242…)**  
  - Parcours complet : Tarifs → Checkout → Paiement → Redirection success
  - Vérifier en base que `profiles` est mis à jour (tier, stripe_customer_id, subscription_status, etc.) et que `user_metadata` n’est **pas** utilisé pour l’abo

- [ ] **Test portail client**  
  - Utilisateur avec abonnement actif → « Gérer mon abonnement » → redirection vers le portail Stripe

- [ ] **Test limite Rookie**  
  - Compte Rookie : 3 analyses puis 403 `limit_reached` et message clair côté frontend (modal + lien /pricing)

- [ ] **Test GET /api/user/subscription**  
  - Réponse contient `tier`, `status`, `billing_period`, `subscription_end_date`, `limits` (dont `analyses_used`)

---

## Post-déploiement

- [ ] **Monitoring des logs configuré**  
  - Logs structurés (JSON) pour les événements webhook (event_type, event_id, user_id si disponible)
  - Alertes sur 5xx ou erreurs répétées sur le webhook

- [ ] **Vérification webhook Stripe**  
  - Dans le tableau de bord Stripe : section Webhooks → derniers événements en succès (200)

---

## Rollback en cas de problème

1. **Désactiver temporairement le webhook**  
   - Stripe Dashboard → Webhooks → désactiver l’endpoint ou supprimer les événements concernés pour éviter des mises à jour incorrectes.

2. **Revenir à une version précédente du backend**  
   - Redéployer la version qui écrivait éventuellement encore dans `user_metadata` si vous aviez une transition, ou la dernière version stable sans la nouvelle logique Stripe.

3. **Corriger les données `profiles` si besoin**  
   - Script ou requêtes SQL ciblées pour remettre `subscription_tier` / `subscription_status` cohérents avec Stripe (ex. via `stripe.Subscription.list(customer=...)` et mise à jour manuelle des lignes concernées).

4. **Réactiver le webhook**  
   - Une fois la cause identifiée et corrigée, réactiver l’endpoint et retester avec un événement de test (Stripe CLI : `stripe trigger checkout.session.completed`).

---

*À cocher au fur et à mesure du déploiement.*
