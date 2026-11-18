# Collecte publique (chantier 3)

Module isolé qui récupère des données **publiques** utiles à ApexAI : calendrier des courses, circuits, plus tard composants et réglages. Il tourne dans GitHub Actions et n'écrit que des fichiers. Il ne touche ni à Railway ni à la base.

## Règles (non négociables)

| Règle | Comment le code la tient |
|---|---|
| Sources publiques uniquement, sans connexion à un compte | Aucune gestion de cookie ni de login dans `polite.py`. |
| Pas de contournement de captcha ni de protection anti-robot | On utilise `httpx` simple. Pas de navigateur furtif, pas d'usurpation d'empreinte : le `Fetcher` de Scrapling (impersonation `curl_cffi`) n'est **pas** utilisé. Un 401, 403, 429 ou une page captcha arrête la collecte de tout le domaine, sans nouvel essai. |
| robots.txt respecté | Lu avant la première page de chaque domaine. S'il est absent (404), rien n'est interdit. S'il est illisible (5xx), on s'abstient. |
| Débit raisonnable | 4 s minimum entre deux requêtes sur un même domaine. Cache disque de 12 h à 7 jours selon la source. |
| Identification honnête | `ApexAIBot/1.0 (+https://www.apexai.racing; contact@apexai.racing)` |
| Jamais LinkedIn, Instagram, Facebook, TikTok, X | Ces domaines sont refusés dans le code, avant toute requête (test `test_domaines_exclus`). |
| Données personnelles | Seulement ce qui décrit un lieu ou un événement. Jamais un nom de pilote, ni un nom ou un email de personne (test `test_circuit_jsonld`). |

Scrapling sert à **lire** les pages HTML, avec `scrapling.parser.Selector`. La récupération reste à notre client poli.

## Sources

| Source | Données | Accès | Conformité vérifiée le 18/11/2026 | Statut |
|---|---|---|---|---|
| **FFSA Karting**, calendrier | Date, lieu, compétition (CdF, Coupe de France, Endurance), catégories, lien vers la page de l'épreuve | JSON public `/ajax/events?year=` : c'est celui que charge la page `/evenement` pour tout visiteur | Pas de robots.txt (404). Pas de donnée personnelle. **Les CGU et mentions légales interdisent la « reproduction et rediffusion » sans autorisation écrite** et renvoient au formulaire de contact, motif « demande de reproduction de contenus ». | ✅ Collecteur prêt et testé sur la vraie source (15 épreuves 2026). ⚠️ **Pas d'affichage dans l'app avant l'autorisation de la FFSA** (modèle de demande plus bas). |
| **OpenStreetMap** (Overpass), circuits | Nom, coordonnées, ville, site web, revêtement, longueur si renseignée | API Overpass, une requête par collecte | Licence ODbL, faite pour la réutilisation. Si on affiche : mention « © les contributeurs d'OpenStreetMap ». Si on republie la base dérivée : même licence. | ✅ Collecteur prêt, testé sur un échantillon. Premier vrai passage à faire dans Actions. Si robots.txt refuse l'API, l'outil s'arrête proprement ; repli : miroir `overpass.openstreetmap.fr` ou extrait Geofabrik. |
| **Sites des circuits**, fiche | Adresse, GPS, téléphone d'accueil, longueur de piste | Page d'accueil ou de contact, analysée par Scrapling (JSON-LD schema.org, puis meta, puis texte) | À vérifier **site par site** avant d'ajouter son URL dans `sources/circuits_seed.json`. | ✅ Analyse prête et testée. Liste d'URL vide pour l'instant (à remplir avec les circuits clients d'abord). |
| Rotax Max Challenge France, IAME Series France, ligues régionales | Calendriers de trophées | Pages publiques | À vérifier : robots.txt, CGU, existence d'un flux (iCal, JSON). | ⏳ Étape 3 |
| Fabricants et revendeurs (châssis, pneus, moteurs) | Catalogue technique : références, cotes, plages de réglage | Pages produit publiques, documents techniques | À vérifier par site. On ne récupère **pas les prix** (risque de conflit avec les revendeurs, et ça ne sert pas le coaching). Partenariat préférable à la collecte pour les fiches de réglage. | ⏳ Étape 4 |
| Résultats de course (FFSA live, Apex Timing…) | Classements, temps | — | **Exclu** : ces données contiennent des noms de pilotes. Règle : jamais un nom de pilote venant d'une source externe dans l'app. | ⛔ |

## Architecture

```
GitHub Actions (manuel)              apexai-backend/collect/
  └─ python -m collect.run  ──▶  polite.py        client poli : robots, délai, cache, refus, journal
                                 sources/
                                   ffsa_events.py   JSON public → épreuves normalisées
                                   osm_circuits.py  Overpass → circuits
                                   circuit_page.py  HTML (Scrapling Selector) → fiche circuit
                                 run.py            écrit staging/*.json + journal.jsonl + resume.json
        └─ artefact du run (30 jours) : on relit avant toute importation
```

- **Isolement.** `collect/` n'importe rien de `src/`, et l'API n'importe rien de `collect/`. Les dépendances sont dans `requirements-collect.txt`, qui n'est jamais installé sur Railway.
- **Zone d'attente.** Aucune écriture en base. L'import dans Supabase sera une étape séparée, sur validation : tables `public_events` / `circuits` alimentées par un script qui lit l'artefact.
- **Alerte de structure.** Si une source attendue revient vide, le run échoue (code 1). La page a sans doute changé, et on regarde avant d'importer quoi que ce soit.

## Coût

| Poste | Coût |
|---|---|
| GitHub Actions | Gratuit sur un dépôt public. Sur un dépôt privé, environ 2 min par run, soit moins de 10 min par mois en hebdomadaire, dans les 2 000 min gratuites. **≈ 0 €** |
| Requêtes | 3 pour la FFSA, 1 pour OSM, 1 par circuit listé |
| Stockage | Artefacts de quelques Ko, gardés 30 jours |
| Scrapling | Libre (BSD-3), utilisé comme simple analyseur HTML |

## Plan par étapes

1. ✅ **Socle et deux sources** (cette PR) : client poli, FFSA, OSM, fiche circuit, tests (19), workflow manuel, artefact.
2. **Premier passage réel dans Actions**, puis relecture de l'artefact. En parallèle : **demande d'autorisation à la FFSA** (modèle ci-dessous).
3. **Import en base** (migration réversible) de `circuits` (OSM, avec attribution) et de `public_events` (FFSA, seulement après accord). Affichage dans l'app derrière un interrupteur : « Prochaines courses près de toi », circuit pré-rempli à l'import d'un fichier de session.
4. Calendriers Rotax, IAME et ligues, après vérification de chaque site.
5. Catalogue technique des composants, en privilégiant les partenariats avec les fabricants.
6. Planning hebdomadaire activé (décommenter `schedule`) une fois les étapes 2 et 3 validées.

## Demande d'autorisation FFSA (à envoyer par Yanis via le formulaire de contact, motif « demande de reproduction de contenus »)

> Bonjour,
>
> Je suis le fondateur d'ApexAI (https://www.apexai.racing), une application française d'analyse de données de karting pour les pilotes, écoles et clubs, à partir de leurs fichiers de session AiM MyChron et Alfano.
>
> Nous souhaiterions afficher dans l'application le calendrier des épreuves fédérales publié sur ffsakarting.org : date, circuit, compétition, catégories, avec un lien vers la page officielle de chaque épreuve. L'objectif est d'aider nos pilotes à préparer leurs courses. Aucun résultat ni aucune donnée de pilote ne serait repris. La source « FFSA Karting » serait citée sur chaque épreuve.
>
> Support envisagé : l'application web https://www.apexai.racing (espace connecté des pilotes).
>
> Pouvez-vous nous indiquer si cet usage est possible, et à quelles conditions ?
>
> Bien cordialement,
> Yanis, ApexAI

## Lancer en local

```bash
pip install -r requirements-collect.txt pytest
python -m pytest collect/tests -q
python -m collect.run --out staging --sources ffsa_events
```
