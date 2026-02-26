# Débogage ordre des virages (V1..V11)

## Logs à regarder dans Railway

Lors d’une analyse, chercher dans les logs les lignes contenant **`[ordre]`** :

1. **`[ordre] AVANT tri — cid, apex1er=, apex_global=`**  
   - Ordre **avant** le tri. `apex1er` = apex sur le 1er tour sélectionné (lap 4), `apex` = index global (df concaténé).  
   - Le tri utilise **apex1er** pour éviter de mélanger des indices de lap 4, 6 et 8.

2. **`[ordre] APRÈS tri (V1..Vn) apex1er tour`**  
   - Ordre **final** : V1=apex1er?, V2=apex1er?, …  
   - Les `apex1er` doivent être **strictement croissants** (ordre du circuit sur le 1er tour).  
   - Si c’est le cas en logs mais que la carte est encore fausse, le souci est côté front ou cache.

3. **`[detect_corners] Ordre par entry_index 1er tour`** (dans geometry)  
   - Ordre des virages **en geometry** (avant refilter).  
   - Utile pour vérifier que la détection elle-même est dans le bon ordre.

## Si l’ordre est encore faux sur la heatmap

### 1. Vérifier les logs

- Les **apex_index** après tri sont-ils croissants ?  
  - **Oui** → le backend envoie le bon ordre ; vérifier que le front n’utilise pas un autre ordre (tri par id, cache, etc.).  
  - **Non** → soit le tri ne s’applique pas (voir ci‑dessous), soit `apex_index` est incohérent (mauvais mapping après refilter).

### 2. Causes possibles côté backend

- **Refilter** : après filtrage des tours (ex. 4, 6, 8), les `apex_index` sont remappés avec `old_to_new`. Si un virage n’a pas d’apex sur les tours sélectionnés, son `apex_index` peut rester ancien ou None → il finit en fin de liste (fallback).
- **Doublons / déduplication** : `unique_by_id` garde un seul virage par `corner_id`. Si deux corners ont le même `corner_id`, l’ordre peut être trompeur.
- **Données manquantes** : si beaucoup de virages ont `apex_index` ou `avg_cumulative_distance` à None, le tri repose sur les fallbacks et peut être mauvais.

### 3. Actions possibles

- Vérifier que **geometry** envoie bien `apex_index` et `avg_cumulative_distance` (et éventuellement `_entry_index_first_lap`) pour chaque virage après refilter.
- Si le df après refilter a des lignes **pas en ordre chronologique** (ex. tri par lap puis par temps), le tri par `apex_index` reflète cet ordre ; il faudrait alors trier le df ou utiliser une autre grandeur (ex. `cumulative_distance` sur un seul tour).
- En dernier recours : trier par **position géographique** (ex. angle polaire autour du centroïde du circuit) pour forcer un ordre de type “tour du circuit”.

## Fichiers concernés

- **Ordre + tri** : `src/api/services.py` (rechercher `[ordre]`, `_sort_key`, `unique_corner_analysis.sort`).
- **Détection + ordre geometry** : `src/analysis/geometry.py` (rechercher `corner_details.sort`, `_entry_index_first_lap`, `avg_cumulative_distance`).
- **Affichage** : `src/visualization/visualization.py` (`plot_corner_heatmap`, `plot_trajectory_2d` utilisent `df.attrs['corner_analysis']` dans l’ordre de la liste).
