#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI — Advisor Service
Calcule les recommandations de pressions pneus à partir des abaques du
catalogue kart_components (plages constructeur par condition), des conditions
de session (météo, températures, grip) et de la signature du circuit
(speed_ratio, bumpiness).

Le format de sortie reprend les clés du frontend (coldPressureFront, ...)
pour une fusion directe avec advisorEngine.ts.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _norm(s: str) -> str:
    """Normalise un nom de produit pour le matching (minuscules, alphanum)."""
    return re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).strip()


def match_tire_component(tire_model: str, components: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Retrouve le pneu du catalogue correspondant au libellé du profil.

    Le profil stocke un libellé libre (ex: "Vega Vert (XH3)") qu'on rapproche
    des lignes catalogue (brand="Vega", name="Vert XH3") par score de tokens.
    """
    target_tokens = set(_norm(tire_model).split())
    if not target_tokens:
        return None

    best, best_score = None, 0.0
    for c in components:
        if c.get("category") != "tire":
            continue
        cand_tokens = set(_norm(f"{c.get('brand','')} {c.get('name','')}").split())
        if not cand_tokens:
            continue
        inter = target_tokens & cand_tokens
        score = len(inter) / len(cand_tokens)
        if score > best_score:
            best, best_score = c, score
    # Au moins la marque + un identifiant de gomme doivent matcher
    return best if best_score >= 0.5 else None


def _pressure_range(specs: Dict[str, Any], condition: str) -> Optional[Tuple[float, float]]:
    ranges = (specs or {}).get("cold_pressure_bar") or {}
    r = ranges.get(condition)
    if isinstance(r, list) and len(r) == 2 and all(isinstance(x, (int, float)) for x in r):
        return float(r[0]), float(r[1])
    return None


STATE_RANK = {"neuf": 2, "rode": 1, "use": 0}
STATE_LABEL = {"neuf": "Neuf", "rode": "Rodé", "use": "Usé"}


def recommend_tire_set(
    tire_sets: List[Dict[str, Any]],
    mode: str,
    weather: str,
) -> Dict[str, Any]:
    """Recommande le train de pneus du stock le plus adapté à la session.

    Logique course :
      - pluie  -> train pluie (alerte si aucun en stock)
      - qualif -> le train le plus frais (perf pure sur peu de tours)
      - course -> un train RODÉ de préférence (constance + endurance),
                  sinon celui avec le plus de vie restante
      - warmup -> le train le plus usé encore roulable (on préserve le stock)
    """
    mode = (mode or "course").lower()
    rain = (weather or "sec").lower() == "pluie"

    usable = [t for t in tire_sets if t.get("active", True)]
    candidates = [t for t in usable if bool(t.get("is_rain")) == rain]

    def life_left(t: Dict[str, Any]) -> int:
        return max(0, int(t.get("laps_life") or 250) - int(t.get("laps_current") or 0))

    def label(t: Dict[str, Any]) -> str:
        model = t.get("custom_model") or t.get("component_label") or ""
        return f"{t.get('label', 'Train')}" + (f" — {model}" if model else "")

    if not candidates:
        if rain:
            return {
                "set": None,
                "message": "⚠️ PLUIE annoncée mais aucun train pluie dans votre stock. "
                           "Déclarez vos pneus pluie dans Mon Kart, ou prévoyez-en l'achat.",
                "priority": "high",
            }
        return {
            "set": None,
            "message": "Aucun train slick actif dans votre stock Mon Kart. Déclarez vos trains pour obtenir une recommandation.",
            "priority": "medium",
        }

    worn_out = [t for t in candidates if life_left(t) <= 0]
    fresh_candidates = [t for t in candidates if life_left(t) > 0] or candidates

    if mode == "qualif":
        best = max(fresh_candidates, key=lambda t: (STATE_RANK.get(t.get("state"), 1), life_left(t)))
        why = "Qualif : on monte le train le plus frais — la performance pure prime sur peu de tours."
    elif mode == "warmup":
        best = min(fresh_candidates, key=lambda t: (STATE_RANK.get(t.get("state"), 1), life_left(t)))
        why = "Warm-up : le train le plus entamé suffit pour la mise en température — on préserve les bons trains."
    else:  # course
        rodes = [t for t in fresh_candidates if t.get("state") == "rode"]
        if rodes:
            best = max(rodes, key=life_left)
            why = "Course : un train rodé (déjà un cycle de chauffe) offre la meilleure constance sur la durée."
        else:
            best = max(fresh_candidates, key=lambda t: (STATE_RANK.get(t.get("state"), 1), life_left(t)))
            why = "Course : pas de train rodé en stock — on prend le plus frais disponible. Astuce : rodez un train en warm-up pour la prochaine course."

    message = f"{label(best)} ({STATE_LABEL.get(best.get('state'), '?')}, {life_left(best)} tours restants). {why}"
    if best in worn_out:
        message += " ⚠️ Ce train a dépassé sa durée de vie : performance dégradée à prévoir."

    return {
        "set": {
            "id": best.get("id"),
            "label": best.get("label"),
            "model": best.get("custom_model") or best.get("component_label"),
            "state": best.get("state"),
            "life_left_laps": life_left(best),
        },
        "message": message,
        "priority": "high" if rain else "medium",
    }


def compute_tire_advice(
    tire_model: str,
    weather: str,
    track_temp: Optional[float],
    air_temp: Optional[float],
    grip: str,
    circuit: Optional[Dict[str, Any]],
    components: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Calcule les pressions à froid/chaud recommandées + justifications."""
    weather = (weather or "sec").lower()
    grip = (grip or "normal").lower()
    circuit = circuit or {}
    condition = {"pluie": "wet", "humide": "damp", "sec": "dry"}.get(weather, "dry")

    tire = match_tire_component(tire_model, components)
    specs = (tire or {}).get("specs") or {}
    compound = specs.get("compound", "medium")
    rationale: List[str] = []

    prange = _pressure_range(specs, condition)
    if tire and prange:
        base = round((prange[0] + prange[1]) / 2, 2)
        rationale.append(
            f"Abaque {tire['brand']} {tire['name']} ({compound}) en piste "
            f"{'sèche' if condition == 'dry' else 'humide' if condition == 'damp' else 'détrempée'} : "
            f"{prange[0]:.2f}–{prange[1]:.2f} bar à froid."
        )
        if condition == "wet" and specs.get("use") == "slick":
            rationale.append("⚠️ Gomme slick sous la pluie : passez sur un train pluie si disponible.")
    else:
        # Fallback sans abaque : bases usuelles par condition
        base = {"dry": 0.68, "damp": 0.85, "wet": 1.10}[condition]
        prange = (base - 0.10, base + 0.10)
        if tire:
            rationale.append(f"{tire['brand']} {tire['name']} : pas d'abaque pour cette condition, base générique {base:.2f} bar.")
        else:
            rationale.append(f"Pneu '{tire_model or 'inconnu'}' hors catalogue : base générique {base:.2f} bar.")
        if condition == "wet":
            rationale.append("PLUIE : pressions hautes pour faire monter la gomme en température et évacuer l'eau.")

    front = rear = base

    # Ajustements thermiques
    if isinstance(track_temp, (int, float)):
        if track_temp > 35:
            front -= 0.04; rear -= 0.04
            rationale.append(f"Piste très chaude ({track_temp:.0f}°C) : -0.04 bar pour anticiper la dilatation.")
        elif track_temp < 15:
            front += 0.05; rear += 0.05
            rationale.append(f"Piste froide ({track_temp:.0f}°C) : +0.05 bar pour atteindre la fenêtre thermique plus vite.")

    # Grip disponible
    if grip == "faible" and condition != "dry":
        front += 0.05; rear += 0.05
        rationale.append("Grip faible : +0.05 bar pour accélérer la montée en température.")
    elif grip == "gommée" and condition == "dry":
        front -= 0.02; rear -= 0.02
        rationale.append("Piste gommée : -0.02 bar, la gomme chauffera d'elle-même.")

    # Signature circuit
    speed_ratio = (circuit.get("speedRatio") or circuit.get("speed_ratio") or "").lower()
    bumpiness = (circuit.get("bumpiness") or "").lower()
    if speed_ratio == "rapide" and condition == "dry":
        front -= 0.02; rear -= 0.02
        rationale.append("Tracé rapide : -0.02 bar, les appuis longs font monter la pression en roulant.")
    elif speed_ratio == "sinueux" and condition == "dry":
        front += 0.02; rear += 0.02
        rationale.append("Tracé sinueux : +0.02 bar, les relances sollicitent moins la carcasse.")
    if bumpiness == "bossele":
        front -= 0.02; rear -= 0.02
        rationale.append("Piste bosselée : -0.02 bar pour assouplir la carcasse.")

    # Clamp dans une enveloppe raisonnable autour de l'abaque
    lo, hi = prange[0] - 0.05, prange[1] + 0.10
    front = round(min(max(front, lo), hi), 2)
    rear = round(min(max(rear, lo), hi), 2)

    # Cible à chaud : delta usuel selon la gomme
    delta_hot = {"soft": 0.15, "medium": 0.18, "hard": 0.20, "wet": 0.10}.get(compound, 0.18)
    hot_front = round(front + delta_hot, 2)
    hot_rear = round(rear + delta_hot, 2)

    message = " ".join(rationale)
    priority = "high" if condition != "dry" or (isinstance(track_temp, (int, float)) and (track_temp > 35 or track_temp < 15)) else "medium"

    recommendations = {
        "coldPressureFront": {"field": "coldPressureFront", "value": front, "message": message, "priority": priority, "suggestedValue": front},
        "coldPressureRear": {"field": "coldPressureRear", "value": rear, "message": message, "priority": priority, "suggestedValue": rear},
        "hotPressureFront": {"field": "hotPressureFront", "value": hot_front, "message": f"Cible à chaud : +{delta_hot:.2f} bar sur le froid (gomme {compound}).", "priority": "low", "suggestedValue": hot_front},
        "hotPressureRear": {"field": "hotPressureRear", "value": hot_rear, "message": f"Cible à chaud : +{delta_hot:.2f} bar sur le froid (gomme {compound}).", "priority": "low", "suggestedValue": hot_rear},
    }

    return {
        "recommendations": recommendations,
        "tire_match": {
            "component_id": tire.get("id") if tire else None,
            "label": f"{tire['brand']} {tire['name']}" if tire else None,
            "compound": compound if tire else None,
            "source": specs.get("source") if tire else None,
        },
    }
