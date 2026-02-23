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
    laps_analyzed: int = 1,
) -> List[Dict[str, Any]]:
    """
    Génère 3-5 conseils hiérarchisés par impact sur la session.
    
    Args:
        df: DataFrame complet avec toutes les colonnes
        corner_details: Liste des détails de chaque virage
        score_data: Dictionnaire avec scores de performance
        corner_analysis: Liste des analyses détaillées par virage
        track_condition: dry | damp | wet | rain — en wet/rain, conseils moins agressifs (freinage)
        laps_analyzed: Nombre de tours sélectionnés pour l'analyse (1 = un seul tour)
    
    Returns:
        Liste de conseils triés par priorité (impact décroissant), info session en premier si laps_analyzed > 1
    """
    advice_list = []
    is_wet = (track_condition or "dry").lower() in ("wet", "rain")

    if laps_analyzed > 1:
        advice_list.append({
            "priority": 0,
            "category": "info",
            "impact_seconds": 0.0,
            "corner": None,
            "message": f"Analyse basée sur {laps_analyzed} tour(s) sélectionné(s) — données agrégées.",
            "explanation": f"Les conseils ci-dessous s'appuient sur les {laps_analyzed} tours analysés.",
            "difficulty": "facile",
        })

    # Enrichir corner_analysis avec labels lisibles si disponibles
    for c in corner_analysis:
        if 'lap' in c and 'corner_id' in c:
            c['label'] = f"Tour {c.get('lap', 1)} / Virage {c.get('corner_id', '?')}"
        else:
            c['label'] = f"Virage {c.get('corner_id', '?')}"

    try:
        # === 1. CONSEILS FREINAGE (moins agressif si piste mouillée) ===
        braking_advice = _generate_braking_advice(corner_analysis, is_wet=is_wet)
        advice_list.extend(braking_advice)
        
        # === 2. CONSEILS APEX ===
        apex_advice = _generate_apex_advice(corner_analysis)
        advice_list.extend(apex_advice)
        
        # === 3. CONSEILS VITESSE ===
        speed_advice = _generate_speed_advice(corner_analysis)
        advice_list.extend(speed_advice)
        
        # === 4. CONSEILS TRAJECTOIRE ===
        trajectory_advice = _generate_trajectory_advice(corner_analysis, df)
        advice_list.extend(trajectory_advice)
        
        # === 5. CONSEILS GLOBAUX (différenciés par score / vitesse / apex_error / direction) ===
        global_advice = _generate_global_advice(score_data, corner_analysis, df, laps_analyzed=laps_analyzed)
        advice_list.extend(global_advice)
        
        # === 6. Conseil spécifique piste mouillée ===
        if is_wet:
            advice_list.append({
                "priority": 4,
                "category": "global",
                "impact_seconds": 0.0,
                "corner": None,
                "message": "Piste mouillée — privilégie la régularité et la fluidité",
                "explanation": "En conditions humides, évite les freinages tardifs et les apex à la limite. Une conduite fluide et prévisible est plus rapide et plus sûre.",
                "difficulty": "moyen",
            })
        
        # Trier : conseils "info" en premier, puis par impact (décroissant)
        advice_list.sort(key=lambda x: (0 if x.get('category') == 'info' else 1, -x.get('impact_seconds', 0)))
        
        # Limiter à top 5 (hors info qui reste en premier)
        info_items = [a for a in advice_list if a.get('category') == 'info']
        rest = [a for a in advice_list if a.get('category') != 'info'][:5]
        return info_items + rest
    
    except Exception as e:
        warnings.warn(f"Error generating coaching advice: {str(e)}")
        return []


def _generate_braking_advice(
    corner_analysis: List[Dict[str, Any]],
    is_wet: bool = False,
) -> List[Dict[str, Any]]:
    """Génère conseils sur le freinage. En piste mouillée, on évite de pousser le freinage tardif."""
    advice = []
    
    for corner in corner_analysis:
        try:
            metrics = corner.get('metrics', {})
            braking_delta = metrics.get('braking_delta', 0.0)
            corner_id = corner.get('corner_id')
            
            if abs(braking_delta) < 2.0:  # Seuil minimum
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
                
                if speed_loss > 5.0:  # Perte > 5 km/h
                    impact_seconds = speed_loss * 0.01
                    message = f"Enchaînement V{corner1.get('corner_id')}→V{corner2.get('corner_id')} : Perte de {speed_loss:.1f} km/h"
                    explanation = f"Sortie de V{corner1.get('corner_id')} à {exit_speed_1:.1f} km/h, mais entrée V{corner2.get('corner_id')} à {entry_speed_2:.1f} km/h. Manques {speed_loss:.1f} km/h de largeur en sortie de V{corner1.get('corner_id')}."
                    
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


def _build_differentiated_corner_advice(
    corner: Dict[str, Any],
    laps_analyzed: int,
) -> Optional[Dict[str, Any]]:
    """
    Construit un conseil unique par virage : différenciation par score, vitesse apex,
    apex_distance_error, corner_type ; gain = time_lost * laps_analyzed ; 3 formulations par catégorie.
    """
    label = corner.get('label', f"Virage {corner.get('corner_id', '?')}")
    score = float(corner.get('score', 70))
    if score >= 80:
        return None
    corner_id = corner.get('corner_id', 0)
    variant = (corner_id or 0) % 3
    apex_speed = float(corner.get('apex_speed_real') or 0.0)
    apex_error = float(corner.get('apex_distance_error') or 0.0)
    time_lost = float(corner.get('time_lost') or 0.0)
    corner_type = (corner.get('corner_type') or "unknown").lower()
    side_fr = "ce droite" if corner_type == "right" else "ce gauche"
    gain_session = time_lost * max(1, laps_analyzed)
    if time_lost < 0.01:
        gain_sentence = ""
    elif time_lost > 0.05:
        gain_sentence = f" Gain potentiel important : {gain_session:.2f}s sur la session."
    else:
        gain_sentence = f" Gain estimé : {gain_session:.2f}s sur la session."
    entry_speed = corner.get('entry_speed')
    target_exit = corner.get('target_exit_speed')
    has_speed_line = entry_speed is not None and float(entry_speed or 0) > 0 and target_exit is not None
    speed_line = (
        f" Vitesse d'entrée actuelle : {float(entry_speed):.0f} km/h → objectif sortie : {float(target_exit):.0f} km/h."
        if has_speed_line else ""
    )

    # Bande vitesse virage (km/h à l'apex)
    if apex_speed < 60:
        speed_band = "slow"
    elif apex_speed <= 90:
        speed_band = "medium"
    else:
        speed_band = "fast"

    # Bandes score
    if score < 65:
        score_band = "low"
    elif score < 80:
        score_band = "mid"
    else:
        score_band = "high"

    # Apex error bandes
    if apex_error > 30:
        error_band = "high"
        error_msg = (
            f"Ton apex est très décalé ({apex_error:.0f}m). Tu rentres trop tôt dans {side_fr} — "
            "attends le point de corde avant de tourner. Conséquence : ta trajectoire de sortie est compromise, "
            "tu perds de la vitesse dans la partie accélération."
        )
        error_msgs = [
            error_msg,
            f"Apex très décalé ({apex_error:.0f}m) dans {side_fr}. Tu engages trop tôt : retarde le braquage jusqu'au point de corde pour une sortie propre.",
            f"Dans {side_fr} ton apex est à {apex_error:.0f}m du bon point. Tu rentres trop tôt ; la sortie en pâtit. Attends le vibreur intérieur avant de tourner.",
        ]
    elif apex_error >= 10:
        error_band = "mid"
        error_msgs = [
            f"Léger décalage d'apex ({apex_error:.0f}m). Retarde légèrement ton point de braquage. Cherche le vibreur intérieur avec la roue avant intérieure.",
            f"Dans {side_fr}, apex décalé de {apex_error:.0f}m. Retarde un peu ton braquage et vise le vibreur avec la roue avant intérieure.",
            f"Apex à {apex_error:.0f}m du bon point. Retarde légèrement le volant et accroche le vibreur intérieur en {side_fr}.",
        ]
    else:
        error_band = "low"
        error_msgs = [
            "Apex précis. Travaille maintenant la vitesse d'approche et la phase d'accélération.",
            f"Apex propre dans {side_fr}. Prochaine étape : attaquer un peu plus à l'entrée et accélérer plus tôt en sortie.",
            "Apex précis. Cherche les dixièmes en entrée (freinage plus tardif) et en sortie (accélération plus précoce).",
        ]
    apex_explanation = error_msgs[variant] + speed_line + gain_sentence

    # Message court + explication selon score_band et speed_band (3 formulations chacune)
    if score_band == "low":
        messages = [
            f"{label} — Problème de trajectoire : point de corde et late apex à travailler",
            f"{label} — Priorité trajectoire : freinage, point de corde, anticipation",
            f"{label} — Trajectoire à corriger : late apex et point de freinage dans {side_fr}",
        ]
        explanations_trajectory = [
            f"Dans {side_fr} le problème principal est la trajectoire. Travaille le point de corde et le late apex : vise l'intérieur avec les yeux, freine plus tard puis tourne une seule fois. " + apex_explanation,
            f"Ce virage demande d'abord une meilleure ligne. Anticipe le point de freinage, atteins le point de corde avant de braquer, puis late apex pour une sortie large. " + apex_explanation,
            f"Trajectoire prioritaire ici : repère un point de freinage fixe, attends le point de corde avant de tourner, et vise le late apex pour libérer la sortie. " + apex_explanation,
        ]
        msg = messages[variant]
        expl = explanations_trajectory[variant]
        difficulty = "moyen"
    elif score_band == "mid":
        messages = [
            f"{label} — Trajectoire OK, vitesse sous-optimale à l'apex",
            f"{label} — Attaque entrée et sortie pour gagner des km/h",
            f"{label} — Maintien de vitesse et traction en sortie à améliorer",
        ]
        if speed_band == "slow":
            expl_base = [
                f"Dans {side_fr} (virage lent) la géométrie est acceptable ; travaille l'attaque à l'entrée et la traction en sortie. Libère le frein progressivement et accélère dès que la trajectoire est engagée. " + apex_explanation,
                f"Virage lent : priorité à l'entrée (plus de vitesse) et à la sortie (traction). Gestion de la traction et relâcher du frein au bon moment. " + apex_explanation,
                f"Ce virage lent peut prendre plus de vitesse. Attaque l'entrée, garde la ligne et pousse l'accélération en sortie. " + apex_explanation,
            ]
        elif speed_band == "fast":
            expl_base = [
                f"Virage rapide : stabilité et confiance. Ne corrige pas en plein virage ; engage une fois et tiens la ligne. " + apex_explanation,
                f"Dans {side_fr} (rapide) priorité à l'engagement : une seule décision, pas de correction en plein virage. Confiance dans le grip. " + apex_explanation,
                f"Virage engagé : fixe ta ligne à l'entrée et ne corrige pas. Gestion de la peur = regard loin et mains stables. " + apex_explanation,
            ]
        else:
            expl_base = [
                f"Équilibre vitesse/trajectoire dans {side_fr}. Trail braking et stabilité en rotation pour garder de la vitesse. " + apex_explanation,
                f"Virage moyen : travaille le trail braking (relâcher le frein en tournant) et la stabilité en rotation. " + apex_explanation,
                f"Dans ce virage moyen, trail braking et une rotation stable te permettront de maintenir plus de vitesse. " + apex_explanation,
            ]
        msg = messages[variant]
        expl = expl_base[variant]
        difficulty = "moyen"
    else:
        messages = [
            f"{label} — Bonne base : régularité et reproduction",
            f"{label} — Reproduis ce virage à chaque tour",
            f"{label} — Cherche les dixièmes restants",
        ]
        expl_base = [
            f"Bonne base dans {side_fr}. Priorité : reproduire exactement cette ligne à chaque tour. Ensuite cherche les dixièmes (entrée plus tardive, sortie plus tôt). " + apex_explanation,
            f"Ce virage est bien négocié. Travaille la régularité : même point de freinage, même apex, même sortie à chaque passage. " + apex_explanation,
            f"Très bien sur {side_fr}. Prochaine étape : régularité puis petits gains (freinage 2–3m plus tard, accélération 1m plus tôt). " + apex_explanation,
        ]
        msg = messages[variant]
        expl = expl_base[variant]
        difficulty = "facile"

    impact_seconds = round(gain_session, 2) if time_lost >= 0.01 else (100 - score) * 0.003
    return {
        "message": msg,
        "explanation": expl,
        "difficulty": difficulty,
        "impact_seconds": round(impact_seconds, 2),
    }


def _generate_global_advice(
    score_data: Dict[str, Any],
    corner_analysis: List[Dict[str, Any]],
    df,
    laps_analyzed: int = 1,
) -> List[Dict[str, Any]]:
    """Génère conseils globaux actionnables avec instructions physiques (différenciés par score/vitesse/apex/direction)."""
    advice = []
    valid_corner_ids = {c.get('corner_id') for c in corner_analysis if c.get('corner_id') is not None}

    try:
        breakdown = score_data.get('breakdown', {})

        # === CONSEILS PAR VIRAGE PROBLÉMATIQUE (différenciés) ===
        corners_valid = [c for c in corner_analysis if c.get('corner_id') in valid_corner_ids]
        worst_corners = sorted(corners_valid, key=lambda c: c.get('score', 100))[:5]

        for corner in worst_corners:
            score = float(corner.get('score', 70))
            if score >= 80:
                continue
            built = _build_differentiated_corner_advice(corner, laps_analyzed)
            if not built:
                continue
            advice.append({
                'priority': len(advice) + 1,
                'category': 'global',
                'impact_seconds': built['impact_seconds'],
                'corner': corner.get('corner_id'),
                'message': built['message'],
                'explanation': built['explanation'],
                'difficulty': built['difficulty'],
            })

        # === CONSTANCE GÉNÉRALE ===
        consistency_score = breakdown.get('trajectory_consistency', 15.0)
        if consistency_score < 15.0 and 'heading' in df.columns:
            heading = pd.to_numeric(df['heading'], errors='coerce').ffill().fillna(0).values
            if len(heading) > 10:
                h = pd.Series(heading)
                smooth = h.rolling(window=10, center=True, min_periods=1).mean()
                diff = np.diff(smooth.values)
                diff = np.where(diff > 180, diff - 360, np.where(diff < -180, diff + 360, diff))
                corrections = int(np.sum(np.abs(diff) > 10.0))  # seuil 10° comme scoring
            else:
                corrections = 0
            if corrections > 10:
                impact_seconds = round((15.0 - consistency_score) * 0.02, 2)
                advice.append({
                    'priority': len(advice) + 1,
                    'category': 'global',
                    'impact_seconds': impact_seconds,
                    'corner': None,
                    'message': f"Fluidité générale — {corrections} corrections de trajectoire détectées",
                    'explanation': (
                        f"{corrections} corrections de volant >10° détectées sur la session. "
                        f"Action : travaille le regard loin (vise la sortie du virage dès l'entrée), "
                        f"ça réduit naturellement les micro-corrections. "
                        f"Mains souples sur le volant — pas de à-coups. "
                        f"Gain estimé : {impact_seconds:.2f}s sur la session."
                    ),
                    'difficulty': 'moyen'
                })

        # === POINT FORT ACTIONNABLE ===
        details = score_data.get('details', {})
        best_corners_ids = details.get('best_corners', [])
        best_corners_ids = [cid for cid in best_corners_ids if cid in valid_corner_ids]
        best_corners_data = [c for c in corner_analysis if c.get('corner_id') in best_corners_ids]

        if best_corners_data:
            best_labels = [c.get('label', f"V{c.get('corner_id')}") for c in best_corners_data[:3]]
            best_str = ', '.join(best_labels)
            
            # Extraire ce qui est bien fait dans ces virages
            avg_speed_best = sum(
                float(c.get('apex_speed_real') or 0)
                for c in best_corners_data[:3]
            ) / max(len(best_corners_data[:3]), 1)

            advice.append({
                'priority': len(advice) + 1,
                'category': 'global',
                'impact_seconds': 0.0,
                'corner': None,
                'message': f"Points forts : {best_str} — Vitesse apex moyenne {avg_speed_best:.0f} km/h",
                'explanation': (
                    f"Tes meilleurs virages ({best_str}) ont une vitesse apex moyenne de "
                    f"{avg_speed_best:.0f} km/h — c'est ton niveau de référence. "
                    f"Identifie ce que tu fais différemment ici : "
                    f"regard, timing freinage, relâcher progressif. "
                    f"Reproduis exactement cette séquence dans les virages similaires."
                ),
                'difficulty': 'facile'
            })

    except Exception as e:
        warnings.warn(f"Error generating global advice: {str(e)}")

    return advice
