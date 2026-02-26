# Handoff — Ordre des virages (V1..V11) sur trajectoire / heatmap

## Contexte utilisateur

- **Problème** : Sur la carte (Trajectoire GPS, Heatmap Virages), les labels V1, V2, … V11 ne suivent pas l’ordre du circuit (premier virage après la ligne = V1, puis V2, etc.). L’utilisateur signale régulièrement « rien dans l’ordre », « c’est toujours pas bon ».
- **Conditions** : Piste 36° sec, tours sélectionnés « bons temps » (ex. tours 4, 6, 8, temps < 50 s). 11 virages détectés après refilter.

## Ce qui a été fait côté code

1. **Geometry** (`src/analysis/geometry.py`)  
   - Détection des virages, tri par `_entry_index_first_lap`, renumérotation 1..n, mise à jour de `df['corner_id']`.  
   - Chaque virage a `avg_cumulative_distance` (position en m sur le circuit), `per_lap_data` (entry_index, apex_index par tour).

2. **Services** (`src/api/services.py`)  
   - Quand `lap_filter` est utilisé (ex. [4, 6, 8]) : refilter des rows et des corners, puis pour chaque corner on remplit `_entry_index_first_lap` et `_apex_index_first_lap` depuis `per_lap_data` **du premier tour sélectionné** (ex. lap 4).  
   - Si un corner n’a **pas** de `per_lap_data` pour ce premier tour, on met en fallback `_apex_index_first_lap = c.get("apex_index")` (index dans le df refiltré, donc lap 6 ou 8).  
   - Tri de `unique_corner_analysis` par :  
     1) `_apex_index_first_lap`,  
     2) `apex_index` global,  
     3) `avg_cumulative_distance`,  
     4) `_entry_index_first_lap` / `entry_index`.  
   - Renumérotation séquentielle V1..V11, mise à jour de `df['corner_id']` et des champs des corners.  
   - Les graphiques (trajectoire, heatmap) utilisent `df.attrs['corner_analysis']` = cette liste triée.

## Cause identifiée avec le JSON (analyse 866faea0)

- Dans l’export **apex-ai-analysis-866faea0.json** :  
  - **V1..V9** ont `per_lap_data` pour les tours 4, 6, 8. Sur le **tour 4**, les `apex_index` sont : 29, 99, 158, 216, 269, 401, 425, 478, 500 → ordre cohérent.  
  - **V10 et V11** n’ont **que** `per_lap_data` pour le **tour 8** (pas de lap 4 ni 6). Donc dans le code actuel :  
    - `_apex_index_first_lap` n’est pas défini depuis le lap 4 ;  
    - on utilise le fallback `c.get("apex_index")` = index dans le df refiltré (ex. 1282, 1504 pour lap 8).  
  - Le tri produit donc : V1..V9 (ordre lap 4), puis V10, V11 (ordre par index global). Si sur le circuit physique V10 et V11 ne sont pas les 10e et 11e virages, ou si leur ordre relatif est inversé, la carte sera encore fausse.

En résumé : **tout corner sans donnée sur le premier tour sélectionné est ordonné via l’index dans le df concaténé (lap 4 + lap 6 + lap 8), ce qui peut donner un mauvais ordre par rapport à la position réelle sur le circuit.**

## Logs utiles (Railway)

- `[ordre] AVANT tri — cid, apex1er=, apex_global=` : ordre avant tri ; voir quels corners ont `apex1er` (lap 4) vs seulement `apex` (global).  
- `[ordre] APRÈS tri (V1..Vn) apex1er tour` : ordre final ; les valeurs doivent être croissantes (ordre circuit).  
- `[detect_corners] Ordre par entry_index 1er tour` (geometry) : ordre des virages en amont.

## Pistes pour Claude / suite

1. **Corners sans données sur le premier tour**  
   - Pour les virages qui n’ont pas de `per_lap_data` pour `min(lap_filter)` : ne pas se baser uniquement sur l’index global.  
   - Utiliser **`avg_cumulative_distance`** (position en m sur le circuit) pour les placer entre les autres virages, ou au moins pour ordonner ces corners entre eux.  
   - S’assurer que `avg_cumulative_distance` est bien propagé depuis geometry jusqu’à `corner_analysis` (y compris après refilter).

2. **Vérifier la cohérence geometry / services**  
   - Après refilter, `corner_details` peut contenir des virages dont `per_lap_data` ne contient plus le premier tour (ex. lap 4 supprimé ou absent). Vérifier que `_apex_index_first_lap` / `_entry_index_first_lap` et `avg_cumulative_distance` restent cohérents et que le tri reste « un tour = une référence » (ex. tout sur lap 4, ou tout sur distance cumulée).

3. **Fallback robuste**  
   - Si ni `_apex_index_first_lap` ni `avg_cumulative_distance` ne sont disponibles pour un corner : log explicite et placer en fin de liste (ou par `entry_index` global) pour éviter des ordres aléatoires.

4. **Frontend / cache**  
   - Si les logs montrent un ordre APRÈS tri correct (apex1er croissants) mais que la carte affiche encore un mauvais ordre : vérifier que le front n’applique pas un tri (ex. par `corner_id`), et qu’il n’y a pas de cache d’anciennes images ou d’ancienne réponse d’analyse.

## Fichiers principaux

- `apexai-backend/src/api/services.py` : refilter, `_apex_index_first_lap` / `_entry_index_first_lap`, tri, renumérotation, `df.attrs['corner_analysis']`.  
- `apexai-backend/src/analysis/geometry.py` : détection, `avg_cumulative_distance`, `per_lap_data`, tri initial.  
- `apexai-backend/src/visualization/visualization.py` : `plot_trajectory_2d`, `plot_corner_heatmap` (lisent `corner_analysis` dans l’ordre de la liste).  
- `apexai-backend/docs/DEBUG_ORDER_VIRAGES.md` : comment lire les logs et quoi faire si l’ordre reste faux.

## Exemple de données (JSON 866faea0)

- **Lap 4 apex_index** (ordre attendu sur le circuit) : 29, 99, 158, 216, 269, 401, 425, 478, 500 (9 premiers virages).  
- **V10** : uniquement `per_lap_data` pour lap 8, `apex_index` 1282.  
- **V11** : uniquement `per_lap_data` pour lap 8, `apex_index` 1504.  
- Utiliser ces valeurs pour reproduire le tri et tester un correctif (ex. tri par `avg_cumulative_distance` pour V10/V11).
