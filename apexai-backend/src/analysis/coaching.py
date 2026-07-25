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
            f"Les temps perdus annoncés sont mesurés sur ces {laps_analyzed} tour(s)."
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
    if is_damp:
        advice_list.append({
            "priority": 0,
            "category": "info",
            "impact_seconds": 0.0,
            "corner": None,
            "message": "Piste humide (damp)",
            "explanation": "Grip réduit d'environ 15-20%. Privilégie des trajectoires qui évitent les bords de piste et les zones à l'ombre. Les freinages doivent être anticipés.",
            "difficulty": "facile",
        })
    if cond == "wet":
        advice_list.append({
            "priority": 0,
            "category": "info",
            "impact_seconds": 0.0,
            "corner": None,
            "message": "Piste mouillée",
            "explanation": "Score ajusté +5 pts (contexte difficile). Priorité à la régularité : chaque erreur coûte plus cher par faible adhérence. Évite les vibreurs et les zones peintes.",
            "difficulty": "facile",
        })
    if is_rain:
        advice_list.append({
            "priority": 0,
            "category": "info",
            "impact_seconds": 0.0,
            "corner": None,
            "message": "Conditions pluvieuses",
            "explanation": "Score ajusté +10 pts. La pluie change tout : vitesses de référence invalides, focuse-toi sur la fluidité et la vision. Anticipe les freinages d'au moins 20% plus tôt.",
            "difficulty": "facile",
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
        rest_ordered = rest_ordered[:3]

        if impact_mult != 1.0:
            for a in rest_ordered:
                a["impact_seconds"] = round(a.get("impact_seconds", 0) * impact_mult, 2)

        if is_rain:
            rest_ordered = [a for a in rest_ordered if a.get("category") != "speed"]

        info_items = [a for a in advice_list if a.get("category") == "info"]
        return info_items + rest_ordered
    
    except Exception as e:
        warnings.warn(f"Error generating coaching advice: {str(e)}")
        return []


def _generate_braking_advice(
    corner_analysis: List[Dict[str, Any]],
    is_wet: bool = False,
    braking_threshold_m: float = 2.0,
) -> List[Dict[str, Any]]:
    """Génère conseils sur le freinage. Seuil plus élevé en damp (5m) pour éviter conseils trop agressifs."""
    advice = []
    for corner in corner_analysis:
        try:
            metrics = corner.get('metrics', {})
            braking_delta = metrics.get('braking_delta', 0.0)
            corner_id = corner.get('corner_id')
            if abs(braking_delta) < braking_threshold_m:
                continue

            # En wet/rain : ne pas conseiller de freiner plus tard (braking_delta < 0 = trop tard déjà)
            if is_wet and braking_delta < 0:
                continue  # Skip "tu freines trop tard" en conditions mouillées

            impact_seconds = abs(braking_delta) * 0.05  # Approximation : 1m = 0.05s
            if is_wet:
                impact_seconds *= 0.5  # Réduire l'impact affiché (moins agressif)
            label = corner.get('label', f"Virage {corner_id}")

            if braking_delta > 0:
                message = f"{label} — Tu freines {braking_delta:.1f}m trop tôt"
                target_entry = corner.get('target_entry_speed') or metrics.get('entry_speed')
                speed_cible = f" Vitesse d'entrée cible : {float(target_entry):.1f} km/h." if target_entry is not None and float(target_entry) > 0 else ""
                explanation = (
                    f"Point de freinage actuel : {metrics.get('braking_point_distance', 0):.1f}m avant l'apex. "
                    f"Point optimal : {metrics.get('braking_point_optimal', 0):.1f}m. "
                    f"En retardant le freinage de {braking_delta:.1f}m, tu gagneras environ {impact_seconds:.2f}s sur la session. "
                    f"Repère un marqueur visuel {braking_delta:.0f}m plus proche de l'apex (bottes de paille, ligne blanche) "
                    f"pour déclencher le freinage.{speed_cible}"
                )
                difficulty = "facile"
            else:
                message = f"{label} — Tu freines {abs(braking_delta):.1f}m trop tard"
                explanation = (
                    f"Point de freinage actuel : {metrics.get('braking_point_distance', 0):.1f}m avant l'apex. "
                    f"Point optimal : {metrics.get('braking_point_optimal', 0):.1f}m. "
                    f"Tu entres trop vite dans ce virage, ce qui te force à corriger en plein apex. "
                    f"Anticipe le freinage de {abs(braking_delta):.1f}m pour stabiliser la trajectoire. "
                    f"Perte estimée : {impact_seconds:.2f}s sur la session."
                )
                difficulty = "moyen"

            advice.append({
                'priority': len(advice) + 1,
                'category': 'braking',
                'impact_seconds': round(impact_seconds, 2),
                'corner': corner_id,
                'message': message,
                'explanation': explanation,
                'difficulty': difficulty,
            })

        except Exception:
            continue

    return advice


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


def _build_differentiated_corner_advice(
    corner: Dict[str, Any],
    laps_analyzed: int,
    speed_ctx: Optional[Dict[str, float]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Un virage = UN conseil, bâti sur la CAUSE DOMINANTE réellement mesurée.

    Toutes les valeurs citées proviennent de la télémétrie : perte de temps
    mesurée (chrono par mini-secteur), écart de point de freinage, erreur de
    placement d'apex (bornée par la largeur de piste), marge de vitesse.
    Aucun chiffre n'est inventé, et les seuils sont RELATIFS au potentiel du
    kart pour rester valables du Mini au KZ.
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
    # 1. Freinage : l'écart au point de freinage optimal est le plus actionnable.
    if abs(braking_delta) >= 2.0:
        if braking_delta > 0:
            return {
                "message": f"{head} — Tu freines {braking_delta:.1f} m trop tôt",
                "explanation": (
                    f"Ton freinage débute {braking_delta:.1f} m avant le point optimal calculé "
                    f"pour ta vitesse d'arrivée ({entry_speed:.0f} km/h). Repère un marqueur fixe "
                    f"(panneau, bordure, changement de revêtement) {braking_delta:.0f} m plus loin "
                    f"et retarde progressivement, tour après tour.{gain_str}{lap_str}"
                ),
                "difficulty": "facile", "impact_seconds": impact_seconds, "category": "braking",
            }
        return {
            "message": f"{head} — Tu freines {abs(braking_delta):.1f} m trop tard",
            "explanation": (
                f"Tu arrives à {entry_speed:.0f} km/h et attaques le freinage {abs(braking_delta):.1f} m "
                f"après le point optimal : tu dois corriger dans le virage, ce qui casse la relance. "
                f"Anticipe et relâche plus progressivement pour garder l'avant posé.{gain_str}{lap_str}"
            ),
            "difficulty": "moyen", "impact_seconds": impact_seconds, "category": "braking",
        }

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
        corners_valid = [c for c in corner_analysis if c.get('corner_id') in valid_corner_ids]

        def _loss(c):
            return float(c.get('time_lost') or 0)

        # Candidats : perte de temps mesurée, ou défaut technique caractérisé.
        def _has_technical_flaw(c):
            metrics = c.get('metrics') or {}
            braking = abs(float(c.get('braking_delta') or metrics.get('braking_delta') or 0))
            apex_err = float(c.get('apex_distance_error') or metrics.get('apex_distance_error') or 0)
            return braking >= 2.0 or apex_err >= 1.0

        candidates = [c for c in corners_valid if _loss(c) > 0.02 or _has_technical_flaw(c)]
        sorted_corners = sorted(candidates, key=_loss, reverse=True)

        for corner in sorted_corners:
            built = _build_differentiated_corner_advice(corner, laps_analyzed, speed_ctx)
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
