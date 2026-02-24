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

    session_msg = f"Analyse basée sur {laps_analyzed} tour(s) — {condition_label}{temp_str}."
    advice_list.append({
        "priority": 0,
        "category": "info",
        "impact_seconds": 0.0,
        "corner": None,
        "message": session_msg,
        "explanation": f"Les conseils ci-dessous s'appuient sur les {laps_analyzed} tour(s) analysés.",
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

    # Enrichir corner_analysis avec labels lisibles si disponibles
    for c in corner_analysis:
        if 'lap' in c and 'corner_id' in c:
            c['label'] = f"Tour {c.get('lap', 1)} / Virage {c.get('corner_id', '?')}"
        else:
            c['label'] = f"Virage {c.get('corner_id', '?')}"

    try:
        braking_threshold_m = 5.0 if is_damp else 2.0
        braking_advice = _generate_braking_advice(corner_analysis, is_wet=is_wet, braking_threshold_m=braking_threshold_m)
        advice_list.extend(braking_advice)

        apex_advice = _generate_apex_advice(corner_analysis)
        advice_list.extend(apex_advice)

        speed_advice = _generate_speed_advice(corner_analysis)
        advice_list.extend(speed_advice)

        trajectory_advice = _generate_trajectory_advice(corner_analysis, df)
        advice_list.extend(trajectory_advice)

        impact_mult = 0.85 if (cond == "dry" and temp is not None and temp < 15) else 1.0
        global_advice = _generate_global_advice(score_data, corner_analysis, df, laps_analyzed=laps_analyzed)
        advice_list.extend(global_advice)

        if impact_mult != 1.0:
            for a in advice_list:
                if a.get("category") != "info":
                    a["impact_seconds"] = round(a.get("impact_seconds", 0) * impact_mult, 2)

        if is_rain:
            advice_list = [a for a in advice_list if a.get("category") != "speed"]

        advice_list.sort(key=lambda x: (0 if x.get("category") == "info" else 1, -x.get("impact_seconds", 0)))

        info_items = [a for a in advice_list if a.get("category") == "info"]
        rest = [a for a in advice_list if a.get("category") != "info"][:5]
        return info_items + rest
    
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
                    message = f"Enchaînement V{n1}→V{n2} : Perte de {speed_loss:.0f} km/h ({exit_speed_1:.0f}→{entry_speed_2:.0f} km/h)"
                    explanation = (
                        f"Tu ne prends pas assez de largeur en sortie de V{n1}, ce qui compresse ta trajectoire d'approche de V{n2}. "
                        f"Sors large de V{n1} pour avoir de l'espace à l'entrée de V{n2}."
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


def _build_differentiated_corner_advice(
    corner: Dict[str, Any],
    laps_analyzed: int,
) -> Optional[Dict[str, Any]]:
    """
    Templates type ingénieur piste : V{n} (ce gauche/ce droite), données réelles, ton impératif.
    Rotation des formulations par corner_id % 3.
    """
    n = corner.get('corner_id', 0) or 0
    label = corner.get('label', f"V{n}")
    score = float(corner.get('score', 70))
    corner_type = (corner.get('corner_type') or "unknown").lower()
    dir_fr = "ce droite" if corner_type == "right" else "ce gauche"
    apex_speed = float(corner.get('apex_speed_real') or 0.0)
    metrics = corner.get('metrics') or {}
    apex_opt = float(corner.get('apex_speed_optimal') or metrics.get('apex_speed_optimal') or apex_speed)
    entry_speed = float(corner.get('entry_speed') or metrics.get('entry_speed') or 0.0)
    apex_error = float(corner.get('apex_distance_error') or metrics.get('apex_distance_error') or 0.0)
    time_lost = float(corner.get('time_lost') or 0.0)
    gain = time_lost * max(1, laps_analyzed)
    delta_speed = max(0.0, apex_opt - apex_speed)
    variant = n % 3
    impact_seconds = round(gain, 2) if time_lost >= 0.01 else round((100 - score) * 0.003, 2)
    gain_str = f" Gain estimé : {gain:.2f}s sur la session." if (time_lost * laps_analyzed) > 0.05 else ""

    if score > 80:
        templates = [
            (f"V{n} {dir_fr} — Bon virage ({score:.0f}/100). Travaille maintenant la constance : reproduis exactement cette trajectoire à chaque tour. Filme-toi si possible pour mémoriser tes repères visuels.", "facile"),
            (f"V{n} {dir_fr} — Bonne performance ({score:.0f}/100). Le gain marginal est dans la vitesse d'entrée : tu peux tenter {entry_speed + 2:.0f} km/h en entrée sur le prochain run.", "facile"),
        ]
        msg, difficulty = templates[variant % 2]
        expl = msg + gain_str
        return {"message": msg, "explanation": expl, "difficulty": difficulty, "impact_seconds": 0.0}

    if 65 <= score <= 80:
        expl = (
            f"V{n} {dir_fr} — Trajectoire correcte mais {delta_speed:.1f} km/h de marge à l'apex. "
            f"Porte ton attention sur la phase d'accélération en sortie : sors plus large pour pouvoir accélérer plus tôt."
        )
        return {
            "message": f"V{n} {dir_fr} — Trajectoire correcte, marge à l'apex",
            "explanation": expl + gain_str,
            "difficulty": "moyen",
            "impact_seconds": impact_seconds,
        }

    if apex_speed < 60 and score < 65 and apex_error > 30:
        templates = [
            f"V{n} {dir_fr} — Tu rentres trop tôt et tu rates l'apex de {apex_error:.0f}m. À {entry_speed:.0f} km/h, ton point de braquage est prématuré : tu pinces l'intérieur trop tôt, ce qui écrase ta sortie. Décale le braquage de 2-3m vers l'avant, vise le vibreur avec la roue avant intérieure.{gain_str}",
            f"V{n} {dir_fr} — Late apex à corriger. Tu traites ce virage en grand rayon uniforme : rentre plus large, braque plus tard, et sors large. L'apex à {apex_error:.0f}m trop tôt te coûte de la traction. Repère un point fixe sur le vibreur intérieur et ne tourne qu'une fois aligné dessus.{gain_str}",
            f"V{n} {dir_fr} — Apex décalé de {apex_error:.0f}m dans un virage à {apex_speed:.0f} km/h. La conséquence directe : tu ne peux pas accélérer avant d'avoir corrigé la trajectoire, ce qui retarde ta relance de plusieurs mètres. Travaille le 'wait and rotate' : attendre, pivoter vite, accélérer.{gain_str}",
        ]
        messages = [
            f"V{n} {dir_fr} — Entrée trop tôt, apex raté de {apex_error:.0f}m",
            f"V{n} {dir_fr} — Late apex à corriger",
            f"V{n} {dir_fr} — Apex décalé de {apex_error:.0f}m, relance retardée",
        ]
        msg, expl = messages[variant], templates[variant]
        return {"message": msg, "explanation": expl, "difficulty": "moyen", "impact_seconds": impact_seconds}

    if 60 <= apex_speed <= 90 and score < 65:
        templates = [
            f"V{n} {dir_fr} — À {entry_speed:.0f} km/h d'entrée, tu perds {apex_error:.0f}m d'apex et {time_lost:.3f}s par passage. C'est un virage de vitesse moyenne qui se passe en trail braking : relâche le frein progressivement en tournant plutôt que de freiner puis tourner.{gain_str}",
            f"V{n} {dir_fr} — Vitesse apex réelle {apex_speed:.0f} km/h vs {apex_opt:.0f} km/h optimal. Tu laisses {delta_speed:.1f} km/h sur la table. Dans ce virage de vitesse moyenne, la fluidité prime : pas de crispation au volant, relâche les épaules en entrée.{gain_str}",
            f"V{n} {dir_fr} — L'écart d'apex ({apex_error:.0f}m) sur ce virage à {apex_speed:.0f} km/h révèle une entrée trop prudente. Tu freines suffisamment mais tu retardes trop le braquage. Avance ton point de rotation de 1-2m.{gain_str}",
        ]
        messages = [
            f"V{n} {dir_fr} — Trail braking à travailler",
            f"V{n} {dir_fr} — {delta_speed:.1f} km/h à l'apex à récupérer",
            f"V{n} {dir_fr} — Braquage trop tardif",
        ]
        msg, expl = messages[variant], templates[variant]
        return {"message": msg, "explanation": expl, "difficulty": "moyen", "impact_seconds": impact_seconds}

    if apex_speed > 90 and score < 65:
        templates = [
            f"V{n} {dir_fr} — Virage engagé à {entry_speed:.0f} km/h. L'apex décalé de {apex_error:.0f}m indique un manque de confiance en entrée : tu te protèges en prenant un rayon plus large. Ce virage se passe en relâchant le frein progressivement (trail braking) tout en amorçant la rotation. Ne cherche pas l'apex immédiatement.{gain_str}",
            f"V{n} {dir_fr} — À {entry_speed:.0f} km/h, chaque mètre d'apex décalé se paye en stabilité de sortie. Tu as {time_lost:.3f}s à récupérer ici. Engage plus tôt, la voiture est stable si tu es progressif. Fixe le vibreur intérieur tôt avec les yeux.{gain_str}",
            f"V{n} {dir_fr} — Virage rapide sous-exploité ({apex_speed:.0f} km/h réel vs {apex_opt:.0f} km/h possible). La peur de l'appui te fait prendre une ligne trop conservatrice. Construis la confiance progressivement : un tour à 95%, puis 97%, puis plein engagement.{gain_str}",
        ]
        messages = [
            f"V{n} {dir_fr} — Manque de confiance, rayon trop large",
            f"V{n} {dir_fr} — Engage plus tôt, stabilité de sortie",
            f"V{n} {dir_fr} — Ligne trop conservatrice",
        ]
        msg, expl = messages[variant], templates[variant]
        return {"message": msg, "explanation": expl, "difficulty": "moyen", "impact_seconds": impact_seconds}

    return None


def _generate_global_advice(
    score_data: Dict[str, Any],
    corner_analysis: List[Dict[str, Any]],
    df,
    laps_analyzed: int = 1,
) -> List[Dict[str, Any]]:
    """Génère conseils globaux actionnables (différenciés par score/vitesse/apex/direction)."""
    advice = []
    valid_corner_ids = {c.get('corner_id') for c in corner_analysis if c.get('corner_id') is not None}

    try:
        breakdown = score_data.get('breakdown', {})

        corners_valid = [c for c in corner_analysis if c.get('corner_id') in valid_corner_ids]
        time_lost_key = lambda c: float(c.get('time_lost') or 0) * max(1, laps_analyzed)
        worst_corners = sorted(corners_valid, key=time_lost_key, reverse=True)[:5]

        for corner in worst_corners:
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
