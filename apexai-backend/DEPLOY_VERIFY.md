# Vérifier le déploiement (tri entry_index + renumérotation corners)

## 1. Redéployer

- **Si Railway est branché sur ce repo** : pousser les changements puis laisser Railway redéployer.
  ```bash
  git add -A && git commit -m "fix: tri corners par entry_index + renumérotation V1..V11 + mapping corner_id"
  git push
  ```
- **Sinon** : dans le dashboard Railway → ton service → **Deployments** → sur le dernier déploiement, cliquer **Redeploy**.

## 2. Vérifier le commit / la date déployés

- **Option A – Dashboard Railway**  
  Deployments → dernier déploiement → tu vois le **commit hash** et la **date/heure** du déploiement.

- **Option B – Endpoint `/health`**  
  Une fois déployé, l’API expose le commit court dans le health check (si Railway injecte `RAILWAY_GIT_COMMIT_SHA`) :
  ```bash
  curl https://TON_BACKEND_RAILWAY.up.railway.app/health
  ```
  Comparer `commit_sha` avec ton dernier commit local :
  ```bash
  git log -1 --format=%h
  ```

## 3. Relancer une analyse

Depuis l’app (frontend), lancer une analyse sur une session qui déclenche la détection des virages.

## 4. Confirmer que la bonne version est en prod

- **Logs Railway**  
  Dans les logs du service, chercher la ligne :
  ```text
  [detect_corners] Ordre par entry_index 1er tour : [V1=idx..., V2=idx..., ...]
  ```
  Si elle apparaît, la version avec le tri par `entry_index` est bien déployée.

- **App (heatmap / tableau)**  
  Vérifier que V1…V11 correspondent bien à l’ordre du circuit (V1 = premier virage après la ligne de départ, etc.).
