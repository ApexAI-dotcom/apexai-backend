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


def _rec(field: str, value: Any, message: str, priority: str = "medium",
         suggested: Any = None) -> Dict[str, Any]:
    return {
        "field": field, "value": value, "message": message,
        "priority": priority,
        "suggestedValue": value if suggested is None else suggested,
    }


def compute_setup_advice(
    weather: str,
    track_temp: Optional[float],
    grip: str,
    circuit: Optional[Dict[str, Any]],
    total_weight: Optional[float],
    chassis_brand: str,
    engine_model: str,
    current_sprocket_front: Optional[int] = None,
    current_sprocket_rear: Optional[int] = None,
) -> Dict[str, Any]:
    """Recommandations châssis / géométrie / transmission / carburation.

    Portage backend de l'advisorEngine frontend : mêmes règles physiques,
    mais alimentées par la signature circuit MESURÉE (télémétrie) et le
    profil Garage lu côté serveur. Source de vérité unique.
    """
    recs: Dict[str, Any] = {}
    is_rain = (weather or "sec").lower() == "pluie"
    grip = (grip or "normal").lower()
    t = float(track_temp) if isinstance(track_temp, (int, float)) else 20.0
    is_hot = t > 35

    c = circuit or {}
    speed_ratio = (c.get("speedRatio") or c.get("speed_ratio") or "mixte")
    hairpins = c.get("hairpinsCount") if c.get("hairpinsCount") is not None else c.get("hairpins_count") or 0
    fast_corners = c.get("fastCornersCount") if c.get("fastCornersCount") is not None else c.get("fast_corners_count") or 0
    elevation = (c.get("elevation") or "plat")
    bumpiness = (c.get("bumpiness") or "lisse")
    is_sinueux = speed_ratio == "sinueux"
    is_rapide = speed_ratio == "rapide"

    chassis_l = (chassis_brand or "").lower()
    engine_l = (engine_model or "").lower()

    # Éléments de contexte réutilisés : chaque recommandation cite les données
    # qui la concernent (tracé mesuré + conditions), jamais un préfixe générique.
    grip_lbl = {"gommée": "gommée", "gommee": "gommée", "faible": "faible"}.get(grip, "normal")
    weather_lbl = {"pluie": "pluie", "humide": "humide"}.get((weather or "sec").lower(), "sèche")
    temp_txt = f"{t:.0f} °C" if isinstance(track_temp, (int, float)) else "température inconnue"
    track_txt = f"tracé {speed_ratio} ({hairpins} épingle(s), {fast_corners} courbe(s) rapide(s))"

    # ── Voies (largeur des trains) ──
    base_rear = 1395 if any(k in chassis_l for k in ("tony", "kosmic", "exprit", "otk", "redspeed")) else 1400
    rear_w, front_w = base_rear, 120
    rear_msg = (f"Piste {weather_lbl} à {temp_txt}, grip {grip_lbl} — châssis {chassis_brand or 'standard'} : "
                f"voie arrière de base {base_rear} mm, largeur neutre qui équilibre le transfert de charge.")
    front_msg = (f"{track_txt.capitalize()} : voie avant standard 120 cm. L'ajustement se déclenche à partir de "
                 f"4 épingles (élargir pour pivoter) ou 4 courbes rapides (rentrer pour stabiliser) — non atteint ici.")
    if is_rain:
        rear_w, front_w = 1360, 125
        rear_msg = (f"PLUIE sur {track_txt} : rentrer le train arrière au minimum (1360 mm) pour forcer le châssis "
                    f"à planter la roue extérieure et retrouver de l'appui.")
        front_msg = ("PLUIE : élargir le train avant au maximum (125 cm) pour un avant incisif qui mord la piste humide. "
                     "ASTUCE : desserrer ou enlever les barres de torsion pour libérer le châssis.")
    else:
        if grip.startswith("gomm"):
            rear_w = min(1400, base_rear + 5)
            rear_msg = (f"Piste gommée à {temp_txt} (adhérence élevée) : élargir à {rear_w} mm pour libérer l'arrière "
                        f"et éviter que le châssis sature en appui.")
        elif grip == "faible":
            rear_w = max(1385, base_rear - 5)
            rear_msg = (f"Grip faible à {temp_txt} : rétrécir à {rear_w} mm pour concentrer la charge sur la roue "
                        f"extérieure et générer du grip mécanique.")
        if is_sinueux or hairpins >= 4:
            front_w = 122
            front_msg = (f"{hairpins} épingle(s) mesurée(s) sur ce {speed_ratio} : élargir l'avant à 122 cm pour engager "
                         f"le kart dans les virages serrés. ASTUCE : retirer la barre de torsion avant pour aider à pivoter.")
        elif fast_corners >= 4:
            front_w = 118
            front_msg = (f"{fast_corners} courbes rapides mesurées (apex moyen élevé) : rentrer l'avant à 118 cm pour "
                         f"limiter l'agressivité et stabiliser le kart à haute vitesse. ASTUCE : insérer la barre de torsion avant.")
    recs["trackWidthRear"] = _rec("trackWidthRear", rear_w, rear_msg, "high" if (is_rain or grip.startswith("gomm")) else "low")
    recs["trackWidthFront"] = _rec("trackWidthFront", front_w, front_msg, "medium")

    # ── Arbre arrière ──
    axle, axle_p = "M", "low"
    axle_msg = (f"Grip {grip_lbl} à {temp_txt} sur piste {weather_lbl} : arbre médium (M), le compromis "
                f"rigidité/souplesse de référence — aucune condition extrême ne justifie de le changer.")
    if is_rain or grip == "faible":
        axle = "S"
        axle_msg = (f"{'PLUIE' if is_rain else f'GRIP FAIBLE à {temp_txt}'} : arbre souple (S) pour faire travailler "
                    f"le châssis en torsion et aller chercher du grip mécanique là où la gomme n'accroche pas.")
        axle_p = "high"
    elif grip.startswith("gomm") and is_hot:
        axle = "H"
        axle_msg = (f"Piste gommée ET chaude ({temp_txt}) : l'adhérence sature le châssis. Arbre dur (H) pour le "
                    f"rigidifier et le forcer à glisser légèrement, sinon il « colle » et étouffe les sorties.")
        axle_p = "high"
    recs["rearAxle"] = _rec("rearAxle", axle, axle_msg, axle_p)

    # ── Géométrie (chasse / carrossage) ──
    caster = "Neutre"
    caster_msg = (f"{hairpins} épingle(s) sur ce {speed_ratio} et grip {grip_lbl} : chasse d'usine (Neutre). "
                  f"Le tracé n'exige pas de forcer le levage de roue arrière intérieure.")
    camber = "Neutre"
    camber_msg = (f"Piste {weather_lbl} à {temp_txt} : carrossage neutre (ou -1 mm), la gomme travaille à plat "
                  f"sur toute la bande de roulement.")
    if is_rain:
        caster, caster_msg = "Max Positif", ("PLUIE : chasse maximale pour charger le train avant et planter les pneus "
                                             "dans l'eau — sans ça l'avant flotte à l'inscription.")
        camber, camber_msg = "Neutre à Positif", ("PLUIE : éviter le carrossage négatif pour poser toute la bande de "
                                                  "roulement et maximiser la surface d'évacuation d'eau.")
    elif hairpins >= 4 and not grip.startswith("gomm"):
        caster, caster_msg = "Positif", (f"{hairpins} épingles mesurées : augmenter la chasse pour soulever la roue "
                                         f"arrière intérieure et faire pivoter le kart dans les serrés.")
    elif grip.startswith("gomm"):
        caster, caster_msg = "Négatif", (f"Piste gommée à {temp_txt} : diminuer la chasse pour ne pas trop lever "
                                         f"l'arrière, ce qui ferait étouffer le moteur en sortie de courbe.")
    recs["caster"] = _rec("caster", caster, caster_msg, "medium")
    recs["camber"] = _rec("camber", camber, camber_msg, "low")

    # ── Hauteurs de caisse ──
    bump_lbl = "bosselé" if bumpiness == "bossele" else "lisse"
    ride = "standard"
    ride_msg = (f"Revêtement {bump_lbl} et piste {weather_lbl} : hauteur de caisse standard. Le centre de gravité "
                f"reste bas, ce qui privilégie la stabilité en appui.")
    if is_rain:
        ride, ride_msg = "haute", ("PLUIE : relever le châssis pour amplifier le transfert de charge dynamique sur la "
                                   "roue extérieure et faire mordre la gomme.")
    elif bumpiness == "bossele":
        ride, ride_msg = "haute", ("Revêtement bosselé mesuré : relever le châssis pour éviter de talonner sur les "
                                   "vibreurs et absorber les irrégularités.")
    ride_p = "medium" if ride != "standard" else "low"
    recs["rideHeightFront"] = _rec("rideHeightFront", ride, ride_msg, ride_p)
    recs["rideHeightRear"] = _rec("rideHeightRear", ride, ride_msg, ride_p)

    # ── Transmission ──
    std_front, std_rear = 12, 80
    if "kz" in engine_l or "tm" in engine_l:
        std_front, std_rear = 17, 26
    elif "micro" in engine_l or "mini" in engine_l:
        std_front, std_rear = 11, 74
    cur_rear = int(current_sprocket_rear) if current_sprocket_rear else std_rear
    cur_front = int(current_sprocket_front) if current_sprocket_front else std_front

    delta, reasons = 0.0, []
    if is_rapide:
        delta -= 1.5; reasons.append("circuit rapide (mesuré)")
    elif is_sinueux:
        delta += 1.5; reasons.append("circuit sinueux (mesuré)")
    if elevation == "vallonne":
        delta += 1; reasons.append("relief vallonné")
    if total_weight and total_weight > 165:
        delta += 1; reasons.append("équipage lourd")
    elif total_weight and 0 < total_weight < 145:
        delta -= 0.5; reasons.append("équipage léger")

    # Arrondi "Math.round" JS (demi vers +inf) pour parité avec l'ancien moteur
    import math
    rounded = int(math.floor(delta + 0.5))
    if rounded != 0:
        final_rear = cur_rear + rounded
        sign = "+" if rounded > 0 else ""
        effect = "plus longue (vitesse de pointe)" if rounded < 0 else "plus courte (relance et couple)"
        recs["sprocketRear"] = _rec("sprocketRear", final_rear,
            f"Passer de {cur_rear} à {final_rear} dents ({sign}{rounded}) : démultiplication {effect}. "
            f"Facteurs retenus — {', '.join(reasons)}.", "high")
    else:
        why_none = ", ".join(reasons) if reasons else "aucun facteur dominant"
        recs["sprocketRear"] = _rec("sprocketRear", cur_rear,
            f"Garder {cur_rear} dents : sur ce {speed_ratio}, les facteurs ({why_none}) se compensent — "
            f"le rapport actuel reste le meilleur compromis relance / vitesse de pointe.", "low")

    ratio_val = cur_rear / cur_front if cur_front else 0
    recs["sprocketFront"] = _rec("sprocketFront", cur_front,
        f"Pignon {cur_front} dents (base {engine_model or 'moteur standard'} : {std_front}/{std_rear}) — "
        f"rapport final {ratio_val:.2f}:1 avec {cur_rear} dents, cohérent pour un {speed_ratio}. "
        f"On ajuste la couronne en priorité, le pignon ne bouge que pour un changement majeur de tracé.", "low")

    # ── Carburation ──
    is_tillotson = any(k in engine_l for k in ("x30", "swift", "60"))
    is_dellorto = any(k in engine_l for k in ("rotax", "tm", "vortex", "junior", "evo", "kz"))
    if is_tillotson:
        high, low = "1T 05m", "1T 15m"
        if t > 28:
            high = "1T 00m"
            msg = "Tillotson (X30) : piste chaude, resserrer la vis H à 1 tour."
        elif t < 15:
            high = "1T 10m"
            msg = "Tillotson (X30) : froid, enrichir la vis H (1T 10m) pour éviter le serrage."
        else:
            msg = "Tillotson (X30) : réglage d'usine (H = 1T 5m, L = 1T 15m)."
        recs["carbConfig"] = _rec("carbConfig", f"H: {high} / L: {low}", msg, "medium",
                                  {"highSpeedScrew": high, "lowSpeedScrew": low})
    elif is_dellorto:
        main_jet, pilot = 125, 60
        if t > 28:
            main_jet = 122
            msg = "Dell'Orto (Rotax/KZ) : forte température, gicleur principal 122 pour ne pas engorger."
        elif t < 15:
            main_jet = 130
            msg = "Dell'Orto (Rotax/KZ) : froid, gicleur principal 130 pour éviter d'être trop pauvre."
        else:
            msg = "Dell'Orto (Rotax/KZ) : gicleur principal 125, ralenti 60."
        recs["carbConfig"] = _rec("carbConfig", f"Gicleur principal: {main_jet}", msg, "medium",
                                  {"mainJet": main_jet, "pilotJet": pilot})

    return recs


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

    mounted = next((t for t in usable if t.get("is_mounted")), None)
    is_change = bool(mounted) and mounted.get("id") != best.get("id")

    best_desc = f"{label(best)} ({STATE_LABEL.get(best.get('state'), '?')}, {life_left(best)} tours restants)"
    if not mounted:
        message = f"Monte le {best_desc}. {why}"
    elif is_change:
        message = f"🔄 Changement recommandé : tu as le {label(mounted)} monté, passe au {best_desc}. {why}"
    else:
        message = f"✔ Le {best_desc} est déjà monté — c'est le bon choix pour cette session. {why}"

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
        "mounted": {
            "id": mounted.get("id"),
            "label": mounted.get("label"),
            "model": mounted.get("custom_model") or mounted.get("component_label"),
        } if mounted else None,
        "is_change": is_change,
        "is_optimal": bool(mounted) and not is_change,
        "message": message,
        "priority": "high" if (rain or is_change) else "medium",
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
