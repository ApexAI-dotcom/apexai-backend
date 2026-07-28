#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - AI Coaching System
Générateur de conseils personnalisés hiérarchisés par impact
"""

from typing import Dict, Any, List, Optional
import warnings
import numpy as np
import pandas as pd


# Nombre de VRAIS conseils (hors encarts d'information). Les encarts ne comptent
# pas dans ce quota : sinon, une séance sous la pluie — qui en ajoute plusieurs —
# n'affichait plus que deux conseils utiles.
MAX_REAL_ADVICE = 4


def generate_coaching_advice(
    df,
    corner_details: List[Dict[str, Any]],
    score_data: Dict[str, Any],
    corner_analysis: List[Dict[str, Any]],
    track_condition: str = "dry",
    track_temperature: Optional[float] = None,
    laps_analyzed: int = 1,
    laps_used: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Génère 3-5 conseils hiérarchisés par impact sur la session.
    track_condition et track_temperature adaptent messages et seuils (damp, wet, rain, froid/chaud).
    """
    advice_list = []
    # Source unique : les mêmes conditions servent au calcul (μ, capacité de
    # freinage) et au discours. Sans ça, le rapport pouvait afficher « pluie »
    # tout en jugeant la séance avec des références de piste sèche.
    from src.analysis.conditions import get_conditions, resolve_conditions
    conditions = get_conditions(df)
    if conditions.condition != (track_condition or "dry").lower():
        conditions = resolve_conditions(track_condition, track_temperature)
    cond = (track_condition or "dry").lower()
    is_wet = cond in ("wet", "rain")
    is_rain = cond == "rain"
    is_damp = cond == "damp"
    temp = track_temperature
    condition_labels = {"dry": "Sec", "damp": "Humide", "wet": "Mouillée", "rain": "Pluie"}
    condition_label = condition_labels.get(cond, "Sec")
    temp_str = f" {temp:.0f}°C" if temp is not None else ""

    # On nomme explicitement les tours retenus : le pilote doit pouvoir
    # retrouver dans SA session les tours sur lesquels les conseils s'appuient.
    laps_txt = ""
    if laps_used:
        nums = ", ".join(str(int(x)) for x in sorted(laps_used))
        laps_txt = f" (tours {nums})"
    session_msg = f"Analyse basée sur {laps_analyzed} tour(s) représentatif(s){laps_txt} — {condition_label}{temp_str}."
    advice_list.append({
        "priority": 0,
        "category": "info",
        "impact_seconds": 0.0,
        "corner": None,
        "message": session_msg,
        "explanation": (
            f"Les tours de sortie et de rentrée des stands, ainsi que les tours ralentis "
            f"(trafic, drapeau), sont écartés : ils fausseraient la comparaison. "
            f"Les temps perdus annoncés sont mesurés sur ces {laps_analyzed} tour(s). "
            f"{conditions.summary()}"
        ),
        "difficulty": "facile",
    })

    if cond == "dry" and temp is not None and temp < 15:
        advice_list.append({
            "priority": 0,
            "category": "info",
            "impact_seconds": 0.0,
            "corner": None,
            "message": f"Piste froide ({temp:.0f}°C)",
            "explanation": "Les pneus nécessitent plusieurs tours pour atteindre leur température optimale. Évite les attaques brusques dans les 3 premiers tours, privilégie des trajectoires plus larges pour chauffer progressivement.",
            "difficulty": "facile",
        })
    elif cond == "dry" and temp is not None and temp > 30:
        advice_list.append({
            "priority": 0,
            "category": "info",
            "impact_seconds": 0.0,
            "corner": None,
            "message": f"Piste chaude ({temp:.0f}°C)",
            "explanation": "Le grip est au maximum mais les pneus peuvent surchauffer sur les sessions longues. Surveille la dégradation en fin de session.",
            "difficulty": "facile",
        })
    # Un seul message par condition : le résumé en tête explique déjà
    # l'adhérence retenue. Empiler trois encarts d'information poussait les
    # VRAIS conseils hors de la liste affichée.
    wet_notes = {
        "damp": ("Piste humide", "Adhérence réduite d'environ 15 %. Évite les bords de piste et "
                                 "les zones à l'ombre, où l'eau reste. Anticipe les freinages."),
        "wet": ("Piste mouillée", "Score ajusté +5 pts (contexte difficile). Priorité à la régularité : "
                                  "chaque erreur coûte plus cher à faible adhérence. Évite les vibreurs "
                                  "et les zones peintes."),
        "rain": ("Conditions pluvieuses", "Score ajusté +10 pts. Les vitesses de référence ne sont plus "
                                          "exploitables : travaille la fluidité, la vision et la trajectoire. "
                                          "Anticipe nettement les freinages."),
    }
    if cond in wet_notes:
        title, body = wet_notes[cond]
        advice_list.append({
            "priority": 0, "category": "info", "impact_seconds": 0.0, "corner": None,
            "message": title, "explanation": body, "difficulty": "facile",
        })

    for c in corner_analysis:
        c['label'] = f"Virage {c.get('corner_id', '?')}"

    try:
        impact_mult = 0.85 if (cond == "dry" and temp is not None and temp < 15) else 1.0
        # Étape 1 — Conseils individuels en priorité absolue (score < 80, triés par time_lost * laps_analyzed)
        global_advice = _generate_global_advice(score_data, corner_analysis, df, laps_analyzed=laps_analyzed)
        # Étape 2 — Enchaînements (perte > 8 km/h entre Vn et Vn+1)
        trajectory_advice = _generate_trajectory_advice(corner_analysis, df)
        enchainement_only = [a for a in trajectory_advice if "Enchaînement" in (a.get("message") or "")]
        # Ordre strict : individuels d'abord, puis enchaînements ; limite à 3 conseils hors info
        rest_ordered = list(global_advice) + list(enchainement_only)
        rest_ordered = rest_ordered[:MAX_REAL_ADVICE]

        if impact_mult != 1.0:
            for a in rest_ordered:
                a["impact_seconds"] = round(a.get("impact_seconds", 0) * impact_mult, 2)

        # Sous la pluie, une vitesse de passage « cible » n'a pas de sens : le
        # grip varie d'un tour à l'autre et d'un point à l'autre de la piste.
        # On garde le freinage, la trajectoire et la régularité.
        if not conditions.allow_speed_push:
            rest_ordered = [a for a in rest_ordered if a.get("category") != "speed"]

        info_items = [a for a in advice_list if a.get("category") == "info"]
        return info_items + rest_ordered
    
    except Exception as e:
        warnings.warn(f"Error generating coaching advice: {str(e)}")
        return []


def _generate_apex_advice(corner_analysis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Génère conseils sur la position des apex."""
    advice = []
    
    for corner in corner_analysis:
        try:
            metrics = corner.get('metrics', {})
            apex_error = metrics.get('apex_distance_error', 0.0)
            direction = metrics.get('apex_direction_error')
            corner_id = corner.get('corner_id')
            
            if apex_error < 1.0:  # Seuil minimum
                continue

            impact_seconds = apex_error * 0.08  # Approximation : 1m = 0.08s
            label = corner.get('label', f"Virage {corner_id}")

            if direction in ["left", "right"]:
                side_fr = "droite" if direction == "left" else "gauche"
                message = f"{label} — Apex décalé de {apex_error:.1f}m vers l'{side_fr}"
                inside = "l'intérieur du virage" if direction == "left" else "l'extérieur du virage"
                explanation = (
                    f"Ta trajectoire clippe l'intérieur avec {apex_error:.1f}m d'erreur. "
                    f"En visant {apex_error:.1f}m plus vers {inside}, "
                    f"tu pourras accélérer {apex_error * 0.05:.2f}s plus tôt en sortie. "
                    f"Gain estimé : {impact_seconds:.2f}s sur la session. "
                    f"Regarde l'apex au moment de tourner le volant, pas la sortie."
                )
            else:
                message = f"{label} — Apex décalé de {apex_error:.1f}m"
                explanation = (
                    f"Position d'apex non optimale ({apex_error:.1f}m d'erreur). "
                    f"Un apex précis te permettrait d'accélérer plus tôt en sortie. "
                    f"Gain estimé : {impact_seconds:.2f}s sur la session."
                )

            difficulty = "moyen" if apex_error < 3.0 else "difficile"

            advice.append({
                'priority': len(advice) + 1,
                'category': 'apex',
                'impact_seconds': round(impact_seconds, 2),
                'corner': corner_id,
                'message': message,
                'explanation': explanation,
                'difficulty': difficulty
            })
        
        except Exception:
            continue
    
    return advice


def _generate_speed_advice(corner_analysis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Génère conseils sur les vitesses apex."""
    advice = []
    
    for corner in corner_analysis:
        try:
            metrics = corner.get('metrics', {})
            speed_real = metrics.get('apex_speed_real', 0.0)
            speed_optimal = metrics.get('apex_speed_optimal', 0.0)
            efficiency = metrics.get('speed_efficiency', 0.8)
            corner_id = corner.get('corner_id')
            
            if speed_optimal <= 0:
                continue
            
            speed_delta = speed_optimal - speed_real
            
            if speed_delta < 3.0:  # Seuil minimum (3 km/h)
                continue

            # Approximation temps perdu : 1 km/h = 0.01s sur un virage moyen
            impact_seconds = speed_delta * 0.01
            efficiency_pct = efficiency * 100
            label = corner.get('label', f"Virage {corner_id}")
            message = f"{label} — {speed_real:.1f} km/h à l'apex vs {speed_optimal:.1f} km/h optimal"
            explanation = (
                f"Vitesse réelle à l'apex : {speed_real:.1f} km/h. "
                f"Vitesse physiquement atteignable sur ce rayon : {speed_optimal:.1f} km/h "
                f"(μ={1.1}, R={1/max(metrics.get('curvature', 0.01), 0.001):.0f}m). "
                f"Tu laisses {speed_delta:.1f} km/h sur la table — c'est {impact_seconds:.2f}s perdu sur la session. "
                f"Efficacité actuelle : {efficiency_pct:.0f}%. "
                f"Pour progresser : plus de fluidité au volant et confiance progressive dans le grip."
            )
            difficulty = "moyen" if speed_delta < 8.0 else "difficile"

            advice.append({
                'priority': len(advice) + 1,
                'category': 'speed',
                'impact_seconds': round(impact_seconds, 2),
                'corner': corner_id,
                'message': message,
                'explanation': explanation,
                'difficulty': difficulty
            })
        
        except Exception:
            continue
    
    return advice


def _generate_trajectory_advice(corner_analysis: List[Dict[str, Any]], df) -> List[Dict[str, Any]]:
    """Génère conseils sur la trajectoire globale."""
    advice = []
    
    try:
        # Détecter patterns de trajectoire
        # Exemple : enchaînements de virages
        if len(corner_analysis) < 2:
            return advice
        
        # Chercher enchaînements consécutifs
        for i in range(len(corner_analysis) - 1):
            corner1 = corner_analysis[i]
            corner2 = corner_analysis[i + 1]
            
            metrics1 = corner1.get('metrics', {})
            metrics2 = corner2.get('metrics', {})
            exit_speed_1 = metrics1.get('exit_speed') or corner1.get('exit_speed') or 0.0
            entry_speed_2 = metrics2.get('entry_speed') or corner2.get('entry_speed') or 0.0
            exit_speed_1 = float(exit_speed_1) if exit_speed_1 is not None else 0.0
            entry_speed_2 = float(entry_speed_2) if entry_speed_2 is not None else 0.0
            
            # Si perte de vitesse importante entre deux virages
            if exit_speed_1 > 0 and entry_speed_2 > 0:
                speed_loss = exit_speed_1 - entry_speed_2
                
                if speed_loss > 8.0:
                    n1, n2 = corner1.get('corner_id'), corner2.get('corner_id')
                    message = f"Enchaînement Virage {n1}→Virage {n2} : Perte de {speed_loss:.0f} km/h ({exit_speed_1:.0f}→{entry_speed_2:.0f} km/h)"
                    explanation = (
                        f"Tu ne prends pas assez de largeur en sortie de Virage {n1}, ce qui compresse ta trajectoire d'approche de Virage {n2}. "
                        f"Sors large de Virage {n1} pour avoir de l'espace à l'entrée de Virage {n2}."
                    )
                    impact_seconds = round(speed_loss * 0.01, 2)
                    
                    advice.append({
                        'priority': len(advice) + 1,
                        'category': 'trajectory',
                        'impact_seconds': round(impact_seconds, 2),
                        'corner': None,  # Conseils entre virages
                        'message': message,
                        'explanation': explanation,
                        'difficulty': 'moyen'
                    })
        
        # Détecter virages avec trajectoire inefficace (double apex)
        for corner in corner_analysis:
            metrics = corner.get('metrics', {})
            entry_speed = metrics.get('entry_speed') or corner.get('entry_speed') or 0.0
            apex_speed = metrics.get('apex_speed_real') or corner.get('apex_speed_real') or 0.0
            exit_speed = metrics.get('exit_speed') or corner.get('exit_speed') or 0.0
            entry_speed = float(entry_speed) if entry_speed is not None else 0.0
            apex_speed = float(apex_speed) if apex_speed is not None else 0.0
            exit_speed = float(exit_speed) if exit_speed is not None else 0.0
            
            # Si perte importante entrée→apex puis récupération apex→sortie
            if entry_speed > 0 and apex_speed > 0 and exit_speed > 0:
                loss_entree = entry_speed - apex_speed
                gain_sortie = exit_speed - apex_speed
                
                if loss_entree > 20 and gain_sortie > 10:  # Pattern double apex
                    impact_seconds = loss_entree * 0.005
                    message = f"Virage {corner.get('corner_id')} : Trajectoire en double apex inefficace"
                    explanation = f"Perte importante en entrée ({loss_entree:.1f} km/h) puis récupération en sortie ({gain_sortie:.1f} km/h). Une trajectoire plus simple (single apex) serait plus rapide."
                    
                    advice.append({
                        'priority': len(advice) + 1,
                        'category': 'trajectory',
                        'impact_seconds': round(impact_seconds, 2),
                        'corner': corner.get('corner_id'),
                        'message': message,
                        'explanation': explanation,
                        'difficulty': 'difficile'
                    })
    
    except Exception as e:
        warnings.warn(f"Error generating trajectory advice: {str(e)}")
    
    return advice


def _speed_context(df) -> Optional[Dict[str, float]]:
    """
    Plage de vitesse RÉELLE de la session.

    Permet de raisonner en relatif : un virage « lent » ou « rapide » n'a pas la
    même vitesse en Mini (pointe ~70 km/h) et en KZ (~130 km/h). Sans ça, des
    seuils absolus (60/90 km/h) rendraient les conseils faux hors d'une seule
    catégorie de kart.
    """
    try:
        if df is None or "speed" not in getattr(df, "columns", []):
            return None
        v = pd.to_numeric(df["speed"], errors="coerce").dropna()
        v = v[v > 5]
        if len(v) < 20:
            return None
        v_min, v_max = float(v.quantile(0.05)), float(v.quantile(0.99))
        if v_max - v_min < 5:
            return None
        return {"v_min": v_min, "v_max": v_max}
    except Exception:
        return None


def _corner_speed_class(apex_speed: float, ctx: Optional[Dict[str, float]]) -> str:
    """Classe le virage (lent / moyen / rapide) RELATIVEMENT au potentiel du kart."""
    if not ctx or apex_speed <= 0:
        return "medium"
    ratio = (apex_speed - ctx["v_min"]) / max(1e-6, ctx["v_max"] - ctx["v_min"])
    if ratio < 0.33:
        return "slow"
    if ratio < 0.66:
        return "medium"
    return "fast"


def _lap_context(corner: Dict[str, Any]) -> str:
    """
    Situe le problème DANS LA SESSION : sur quel tour le pilote a réussi ce
    virage, sur lequel il a perdu, et si le défaut se répète. Sans cela, le
    pilote ne sait pas où regarder dans ses tours.
    """
    best = corner.get("best_lap_here")
    worst = corner.get("worst_lap_here")
    spread = corner.get("lap_spread_s") or 0.0
    if best is None:
        return ""
    if corner.get("recurring"):
        return (f" Défaut récurrent : tu perds sur la plupart de tes tours "
                f"(ton meilleur passage ici : tour {best}).")
    if spread > 0.05 and worst is not None and worst != best:
        return (f" Ton meilleur passage ici : tour {best} ; le plus coûteux : "
                f"tour {worst} ({spread:.2f}s d'écart).")
    return f" Ton meilleur passage ici : tour {best}."


def _braking_advice(
    corner: Dict[str, Any],
    head: str,
    gain_str: str,
    lap_str: str,
    impact_seconds: float,
    conditions=None,
) -> Optional[Dict[str, Any]]:
    """
    Conseil de freinage, si et seulement si le virage se freine vraiment.

    L'ordre des tests suit celui d'un ingénieur de piste : on ne demande pas à
    quelqu'un de freiner plus tard tant qu'il n'appuie pas assez fort. Chaque
    conseil cite le tour de référence — un passage que le pilote a signé
    lui-même, donc reproductible, et vérifiable sur la carte.
    """
    if not corner.get("has_braking_zone"):
        return None

    # Piste mouillée : retarder ou durcir un freinage envoie le kart tout droit.
    # On ne transforme pas un conseil de performance en prise de risque — il
    # reste le temps mort et la régularité, qui paient autant et sans danger.
    allow_attack = True if conditions is None else bool(conditions.allow_brake_later)

    def _f(key, default=0.0):
        v = corner.get(key)
        return float(v) if v is not None else float(default)

    verdict = corner.get("braking_verdict") or "optimal"
    point = _f("braking_point_distance")
    best_point = _f("braking_best_point_m")
    best_lap = corner.get("braking_best_lap")
    delta = _f("braking_delta")
    peak = _f("braking_peak_g")
    capability = _f("braking_capability_g")
    coasting = _f("coasting_s")
    spread = _f("braking_consistency_m")
    entry = _f("braking_entry_speed")
    v_min = _f("braking_min_speed")
    theo = _f("braking_theoretical_min_m")
    window_loss = _f("braking_time_lost")
    # Le gain annoncé reste la perte chronométrée DU VIRAGE, celle qu'affiche
    # l'étiquette de la carte. Le temps perdu sur la seule zone de freinage en
    # est une décomposition, citée dans le texte et jamais additionnée.
    impact = impact_seconds
    share = (f" Sur la seule zone de freinage, l'écart chronométré est de "
             f"{window_loss:.2f} s." if 0.02 < window_loss <= max(impact_seconds, 0.0) + 1e-9 else "")
    ref = f" (référence : ton tour {best_lap})" if best_lap else ""

    # 1. Intensité insuffisante : la crête, pas le point, est le vrai défaut.
    if verdict == "soft" and capability > 0 and allow_attack:
        return {
            "message": f"{head} — Freinage trop mou : {peak:.2f} g",
            "explanation": (
                f"Tu ne dépasses pas {peak:.2f} g ici alors que tu as démontré {capability:.2f} g "
                f"ailleurs sur la session. À {entry:.0f} km/h, la physique autorise {theo:.0f} m "
                f"pour descendre à {v_min:.0f} km/h ; tu en utilises {point:.0f}. "
                f"Attaque la pédale plus franchement dès le premier appui : c'est ce qui te "
                f"permettra ensuite de retarder le point.{share}{gain_str}{lap_str}"
            ),
            "difficulty": "moyen", "impact_seconds": impact, "category": "braking",
        }

    # 2. Temps mort : ni frein ni gaz, du temps perdu pur.
    if verdict == "coasting":
        best_coast = _f("coasting_best_s")
        excess = _f("coasting_excess_s")
        return {
            "message": f"{head} — {coasting:.2f} s sans frein ni gaz",
            "explanation": (
                f"Entre le relâcher de frein et la remise des gaz, tu roules {coasting:.2f} s "
                f"en roue libre, contre {best_coast:.2f} s sur ton passage le plus rapide ici"
                f"{ref} : {excess:.2f} s de plus, chaque tour. Un kart n'a pas de transfert de "
                f"masse à attendre — enchaîne frein puis gaz sans palier, quitte à relâcher le "
                f"frein plus progressivement à l'inscription.{share}{gain_str}{lap_str}"
            ),
            "difficulty": "moyen", "impact_seconds": impact, "category": "braking",
        }

    # 3. Point de freinage, comparé à SON meilleur passage sur ce virage.
    if verdict == "brake_later" and allow_attack:
        return {
            "message": f"{head} — Tu freines {delta:.0f} m plus tôt que ton meilleur tour",
            "explanation": (
                f"Ici tu déclenches à {point:.0f} m de l'apex, alors que tu as déjà freiné à "
                f"{best_point:.0f} m{ref} en gardant la même vitesse de passage "
                f"({v_min:.0f} km/h). Ce n'est donc pas une prise de risque : tu l'as déjà fait. "
                f"Prends un repère fixe au bord de piste et avance-le de {delta:.0f} m."
                f"{share}{gain_str}{lap_str}"
            ),
            "difficulty": "facile", "impact_seconds": impact, "category": "braking",
        }

    if verdict == "brake_earlier":
        return {
            "message": f"{head} — Ton meilleur passage freinait {abs(delta):.0f} m plus tôt",
            "explanation": (
                f"Tu déclenches à {point:.0f} m de l'apex, mais ton passage le plus rapide ici "
                f"freinait à {best_point:.0f} m{ref} — plus tôt, et pourtant plus rapide sur la "
                f"portion. Anticiper te laisse le temps de rendre les freins avant l'inscription : "
                f"tu ressors mieux placé, et c'est la sortie qui paie sur la ligne droite suivante. "
                f"Essaie de reproduire ce repère.{share}{gain_str}{lap_str}"
            ),
            "difficulty": "moyen", "impact_seconds": impact, "category": "braking",
        }

    # 4. Régularité : à niveau égal, c'est ce qui sépare deux pilotes.
    if verdict == "inconsistent":
        return {
            "message": f"{head} — Point de freinage instable (± {spread:.0f} m)",
            "explanation": (
                f"D'un tour à l'autre, ton déclenchement varie de {spread:.0f} m. Un pilote "
                f"confirmé tient 2 à 3 m. Cette dispersion t'oblige à corriger différemment à "
                f"chaque passage, et rend le virage imprévisible. Choisis UN repère visuel fixe "
                f"et n'en change plus de la session.{share}{gain_str}{lap_str}"
            ),
            "difficulty": "facile", "impact_seconds": impact, "category": "braking",
        }

    return None


def _build_differentiated_corner_advice(
    corner: Dict[str, Any],
    laps_analyzed: int,
    speed_ctx: Optional[Dict[str, float]] = None,
    conditions=None,
) -> Optional[Dict[str, Any]]:
    """
    Un virage = UN conseil, bâti sur la CAUSE DOMINANTE réellement mesurée.

    Toutes les valeurs citées proviennent de la télémétrie : perte de temps
    mesurée (chrono par mini-secteur), écart de point de freinage, erreur de
    placement d'apex (bornée par la largeur de piste), marge de vitesse.
    Aucun chiffre n'est inventé, et les seuils sont RELATIFS au potentiel du
    kart pour rester valables du Mini au KZ — et aux CONDITIONS DE PISTE, pour
    rester valables du sec à la pluie battante.
    """
    n = corner.get('corner_id', 0) or 0
    virage_label = f"Virage {n}"
    corner_type = (corner.get('corner_type') or "unknown").lower()
    dir_fr = "à droite" if corner_type == "right" else "à gauche" if corner_type == "left" else ""
    head = f"{virage_label} {dir_fr}".strip()

    metrics = corner.get('metrics') or {}
    def _m(key, default=0.0):
        return float(corner.get(key) if corner.get(key) is not None else metrics.get(key, default) or default)

    score = float(corner.get('score', 70) or 70)
    apex_speed = _m('apex_speed_real')
    apex_opt = _m('apex_speed_optimal') or apex_speed
    entry_speed = _m('entry_speed')
    apex_error = _m('apex_distance_error')
    braking_delta = _m('braking_delta')
    time_lost = float(corner.get('time_lost') or 0.0)
    delta_speed = max(0.0, apex_opt - apex_speed)

    impact_seconds = round(time_lost, 3)
    gain_str = f" Gain mesuré : {time_lost:.2f}s par tour." if time_lost > 0.02 else ""
    lap_str = _lap_context(corner)
    speed_class = _corner_speed_class(apex_speed, speed_ctx)

    # Marge de vitesse jugée en RELATIF (2,5 % de la vitesse de passage),
    # pour ne pas dépendre de la cylindrée.
    speed_gap_significant = apex_speed > 0 and delta_speed >= max(1.5, 0.025 * apex_speed)

    # ── Cause dominante ──────────────────────────────────────────────────────
    # 1. Freinage. Toutes les valeurs viennent de `src.analysis.braking`, la même
    # source que la pastille et la bande de la carte : le pilote peut aller
    # vérifier chaque chiffre à l'écran.
    brk = _braking_advice(corner, head, gain_str, lap_str, impact_seconds, conditions)
    if brk:
        return brk

    # 2. Placement d'apex (mesure bornée par la largeur de piste).
    if apex_error >= 1.0:
        return {
            "message": f"{head} — Apex manqué de {apex_error:.1f} m",
            "explanation": (
                f"Ton point de corde est décalé de {apex_error:.1f} m par rapport au point optimal "
                f"du virage. Fixe l'apex du regard AVANT de braquer : la trajectoire suit le regard. "
                f"Un apex propre ouvre le volant plus tôt et allonge la phase d'accélération."
                f"{gain_str}{lap_str}"
            ),
            "difficulty": "moyen", "impact_seconds": impact_seconds, "category": "apex",
        }

    # 3. Vitesse de passage (relative au potentiel du kart).
    if speed_gap_significant:
        if speed_class == "slow":
            how = ("Relâche les freins plus progressivement à l'inscription (trail braking) : "
                   "l'avant reste chargé et le kart tourne sans que tu perdes de vitesse.")
        elif speed_class == "fast":
            how = ("Sur un virage rapide, la perte vient presque toujours d'un lever de pied "
                   "de sécurité. Vise l'apex du regard et garde le pied constant.")
        else:
            how = ("Élargis ton entrée pour ouvrir le rayon : tu pourras passer plus vite à l'apex "
                   "sans élargir en sortie.")
        return {
            "message": f"{head} — {delta_speed:.1f} km/h à reprendre à l'apex",
            "explanation": (
                f"Tu passes à {apex_speed:.0f} km/h alors que ton meilleur passage sur ce virage "
                f"est à {apex_opt:.0f} km/h : la vitesse est atteignable, tu l'as déjà faite. {how}"
                f"{gain_str}{lap_str}"
            ),
            "difficulty": "moyen" if speed_class != "fast" else "difficile",
            "impact_seconds": impact_seconds, "category": "speed",
        }

    # 4. Rien de précis à corriger mais du temps perdu : régularité.
    if time_lost > 0.02:
        return {
            "message": f"{head} — Manque de régularité",
            "explanation": (
                f"Aucun défaut technique marqué ici : ta trajectoire et ton freinage sont bons, "
                f"mais tu ne les reproduis pas à l'identique.{gain_str}{lap_str} "
                f"Reproduis exactement les repères de ton meilleur passage."
            ),
            "difficulty": "moyen", "impact_seconds": impact_seconds, "category": "consistency",
        }

    # 5. Virage réussi : on le signale, sans le faire passer pour une priorité.
    if score > 80:
        return {
            "message": f"{head} — Passage maîtrisé",
            "explanation": (
                f"Rien à corriger : {apex_speed:.0f} km/h à l'apex, trajectoire propre, "
                f"aucune perte de temps mesurée. Sers-t'en comme référence de sensations."
            ),
            "difficulty": "facile", "impact_seconds": 0.0, "category": "info",
        }

    return None


def _generate_global_advice(
    score_data: Dict[str, Any],
    corner_analysis: List[Dict[str, Any]],
    df,
    laps_analyzed: int = 1,
) -> List[Dict[str, Any]]:
    """
    Conseils par virage, classés par TEMPS RÉELLEMENT PERDU.

    On ne filtre plus sur le « score » : un virage peut avoir un bon score et
    rester le plus coûteux de la session — c'est celui-là que le pilote doit
    travailler en premier. Un virage sans perte mesurée ni défaut technique
    n'est jamais présenté comme une priorité.
    """
    advice = []
    valid_corner_ids = {c.get('corner_id') for c in corner_analysis if c.get('corner_id') is not None}

    try:
        speed_ctx = _speed_context(df)
        # Conditions de piste : elles décident de ce qu'on a le droit de
        # conseiller. Lues sur la session, pas redéclarées ici.
        from src.analysis.conditions import get_conditions
        conditions = get_conditions(df)
        corners_valid = [c for c in corner_analysis if c.get('corner_id') in valid_corner_ids]

        def _loss(c):
            return float(c.get('time_lost') or 0)

        # Candidats : perte de temps mesurée, ou défaut technique caractérisé.
        def _has_technical_flaw(c):
            metrics = c.get('metrics') or {}
            apex_err = float(c.get('apex_distance_error') or metrics.get('apex_distance_error') or 0)
            if apex_err >= 1.0:
                return True
            if not c.get('has_braking_zone'):
                return False
            # Les défauts de freinage que l'analyse sait mesurer : intensité,
            # temps mort, point de déclenchement, régularité.
            return c.get('braking_verdict') in (
                "soft", "coasting", "brake_later", "brake_earlier", "inconsistent"
            )

        candidates = [c for c in corners_valid if _loss(c) > 0.02 or _has_technical_flaw(c)]
        sorted_corners = sorted(candidates, key=_loss, reverse=True)

        for corner in sorted_corners:
            built = _build_differentiated_corner_advice(corner, laps_analyzed, speed_ctx, conditions)
            if not built:
                continue
            advice.append({
                'priority': len(advice) + 1,
                'category': built.get('category', 'global'),
                'impact_seconds': built['impact_seconds'],
                'corner': corner.get('corner_id'),
                'message': built['message'],
                'explanation': built['explanation'],
                'difficulty': built['difficulty'],
            })

    except Exception as e:
        warnings.warn(f"Error generating global advice: {str(e)}")

    return advice
