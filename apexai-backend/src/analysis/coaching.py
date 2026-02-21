#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - AI Coaching System
Générateur de conseils personnalisés hiérarchisés par impact
"""

from typing import Dict, Any, List, Optional
import warnings


def generate_coaching_advice(
    df,
    corner_details: List[Dict[str, Any]],
    score_data: Dict[str, Any],
    corner_analysis: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Génère 3-5 conseils hiérarchisés par impact sur le temps au tour.
    
    Args:
        df: DataFrame complet avec toutes les colonnes
        corner_details: Liste des détails de chaque virage
        score_data: Dictionnaire avec scores de performance
        corner_analysis: Liste des analyses détaillées par virage
    
    Returns:
        Liste de conseils triés par priorité (impact décroissant)
    """
    advice_list = []

    # Enrichir corner_analysis avec labels lisibles si disponibles
    for c in corner_analysis:
        if 'lap' in c and 'corner_id' in c:
            c['label'] = f"Tour {c.get('lap', 1)} / Virage {c.get('corner_id', '?')}"
        else:
            c['label'] = f"Virage {c.get('corner_id', '?')}"

    try:
        # === 1. CONSEILS FREINAGE ===
        braking_advice = _generate_braking_advice(corner_analysis)
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
        
        # === 5. CONSEILS GLOBAUX ===
        global_advice = _generate_global_advice(score_data, corner_analysis, df)
        advice_list.extend(global_advice)
        
        # Trier par impact (décroissant)
        advice_list.sort(key=lambda x: x.get('impact_seconds', 0), reverse=True)
        
        # Limiter à top 5
        return advice_list[:5]
    
    except Exception as e:
        warnings.warn(f"Error generating coaching advice: {str(e)}")
        return []


def _generate_braking_advice(corner_analysis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Génère conseils sur le freinage."""
    advice = []
    
    for corner in corner_analysis:
        try:
            metrics = corner.get('metrics', {})
            braking_delta = metrics.get('braking_delta', 0.0)
            corner_id = corner.get('corner_id')
            
            if abs(braking_delta) < 2.0:  # Seuil minimum
                continue

            impact_seconds = abs(braking_delta) * 0.05  # Approximation : 1m = 0.05s
            label = corner.get('label', f"Virage {corner_id}")

            if braking_delta > 0:
                message = f"{label} — Tu freines {braking_delta:.1f}m trop tôt"
                explanation = (
                    f"Point de freinage actuel : {metrics.get('braking_point_distance', 0):.1f}m avant l'apex. "
                    f"Point optimal : {metrics.get('braking_point_optimal', 0):.1f}m. "
                    f"En retardant le freinage de {braking_delta:.1f}m, tu gagneras environ {impact_seconds:.2f}s par tour. "
                    f"Repère un marqueur visuel {braking_delta:.0f}m plus proche de l'apex (bottes de paille, ligne blanche) "
                    f"pour déclencher le freinage. Vitesse d'entrée cible : {metrics.get('entry_speed', 0):.1f} km/h."
                )
                difficulty = "facile"
            else:
                message = f"{label} — Tu freines {abs(braking_delta):.1f}m trop tard"
                explanation = (
                    f"Point de freinage actuel : {metrics.get('braking_point_distance', 0):.1f}m avant l'apex. "
                    f"Point optimal : {metrics.get('braking_point_optimal', 0):.1f}m. "
                    f"Tu entres trop vite dans ce virage, ce qui te force à corriger en plein apex. "
                    f"Anticipe le freinage de {abs(braking_delta):.1f}m pour stabiliser la trajectoire. "
                    f"Perte estimée : {impact_seconds:.2f}s par tour."
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
                    f"Gain estimé : {impact_seconds:.2f}s par tour. "
                    f"Regarde l'apex au moment de tourner le volant, pas la sortie."
                )
            else:
                message = f"{label} — Apex décalé de {apex_error:.1f}m"
                explanation = (
                    f"Position d'apex non optimale ({apex_error:.1f}m d'erreur). "
                    f"Un apex précis te permettrait d'accélérer plus tôt en sortie. "
                    f"Gain estimé : {impact_seconds:.2f}s par tour."
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
                f"Tu laisses {speed_delta:.1f} km/h sur la table — c'est {impact_seconds:.2f}s perdu par tour. "
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
            
            exit_speed_1 = metrics1.get('exit_speed', 0.0)
            entry_speed_2 = metrics2.get('entry_speed', 0.0)
            
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
            entry_speed = metrics.get('entry_speed', 0.0)
            apex_speed = metrics.get('apex_speed_real', 0.0)
            exit_speed = metrics.get('exit_speed', 0.0)
            
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


def _generate_global_advice(
    score_data: Dict[str, Any],
    corner_analysis: List[Dict[str, Any]],
    df
) -> List[Dict[str, Any]]:
    """Génère conseils globaux actionnables avec instructions physiques."""
    advice = []
    valid_corner_ids = {c.get('corner_id') for c in corner_analysis if c.get('corner_id') is not None}

    try:
        breakdown = score_data.get('breakdown', {})

        # === CONSEILS PAR VIRAGE PROBLÉMATIQUE ===
        # Trier par score croissant (pires virages en premier), uniquement virages présents
        corners_valid = [c for c in corner_analysis if c.get('corner_id') in valid_corner_ids]
        worst_corners = sorted(corners_valid, key=lambda c: c.get('score', 100))[:3]

        for corner in worst_corners:
            label = corner.get('label', f"Virage {corner.get('corner_id', '?')}")
            score = corner.get('score', 70)
            
            if score >= 80:
                continue  # Pas besoin de conseil si bon score

            speed_real = float(corner.get('apex_speed_real') or 0.0)
            speed_optimal = float(corner.get('apex_speed_optimal') or 0.0)
            speed_delta = max(0, speed_optimal - speed_real)
            apex_error = float(corner.get('apex_distance_error') or 0.0)
            direction = corner.get('apex_direction_error') or ''
            entry_speed = float(corner.get('entry_speed') or 0.0)
            exit_speed = float(corner.get('exit_speed') or 0.0)
            corner_type = corner.get('corner_type', 'unknown')
            lateral_g = float(corner.get('lateral_g_max') or 0.0)
            
            # Construire conseil actionnable selon le problème principal
            impact_seconds = (100 - score) * 0.003

            # Déterminer le problème principal
            if speed_delta > 5.0:
                # Problème de vitesse apex
                side = "droite" if corner_type == "right" else "gauche"
                message = f"{label} — Perds {speed_delta:.1f} km/h à l'apex ({speed_real:.0f} vs {speed_optimal:.0f} km/h optimal)"
                explanation = (
                    f"Tu arrives trop lentement à l'apex de ce virage à {side}. "
                    f"Action : retarde ton freinage de 5-10m, puis libère progressivement "
                    f"la pression de frein en approchant de l'apex pour maintenir {speed_delta:.0f} km/h de plus. "
                    f"Ton G latéral max est {lateral_g:.1f}G — le grip est disponible, "
                    f"fais confiance aux pneus. "
                    f"Gain estimé : {impact_seconds:.2f}s par tour."
                )
                difficulty = "moyen"

            elif apex_error > 2.0:
                # Problème de placement apex
                side_action = "serre l'intérieur plus tôt" if direction == 'late' else "patiente avant de tourner"
                message = f"{label} — Apex décalé de {apex_error:.1f}m, trajectoire à corriger"
                explanation = (
                    f"Ta ligne n'est pas optimale dans ce virage. "
                    f"Action : {side_action}. "
                    f"Repère un point fixe à l'intérieur du virage (vibreur, marque) "
                    f"et vise-le précisément avec les yeux AVANT de tourner le volant. "
                    f"Vitesse d'entrée actuelle : {entry_speed:.0f} km/h → "
                    f"objectif sortie : {exit_speed + speed_delta:.0f} km/h. "
                    f"Gain estimé : {impact_seconds:.2f}s par tour."
                )
                difficulty = "moyen"

            else:
                # Problème général de constance
                message = f"{label} — Score {score}/100, manque de régularité"
                explanation = (
                    f"Ce virage est irrégulier d'un tour à l'autre. "
                    f"Action : choisis UN point de repère fixe pour le freinage "
                    f"(pancarte, marque au sol) et engage-toi à l'utiliser à chaque tour. "
                    f"Vitesse apex actuelle : {speed_real:.0f} km/h. "
                    f"Priorité : constance avant vitesse."
                )
                difficulty = "facile"

            advice.append({
                'priority': len(advice) + 1,
                'category': 'global',
                'impact_seconds': round(impact_seconds, 2),
                'corner': corner.get('corner_id'),
                'message': message,
                'explanation': explanation,
                'difficulty': difficulty
            })

        # === CONSTANCE GÉNÉRALE ===
        consistency_score = breakdown.get('trajectory_consistency', 15.0)
        if consistency_score < 15.0 and 'heading' in df.columns:
            heading = df['heading'].diff().abs()
            corrections = int((heading > 5.0).sum())
            if corrections > 10:
                impact_seconds = round((15.0 - consistency_score) * 0.02, 2)
                advice.append({
                    'priority': len(advice) + 1,
                    'category': 'global',
                    'impact_seconds': impact_seconds,
                    'corner': None,
                    'message': f"Fluidité générale — {corrections} corrections de trajectoire détectées",
                    'explanation': (
                        f"{corrections} corrections de volant >5° détectées sur le tour. "
                        f"Action : travaille le regard loin (vise la sortie du virage dès l'entrée), "
                        f"ça réduit naturellement les micro-corrections. "
                        f"Mains souples sur le volant — pas de à-coups. "
                        f"Gain estimé : {impact_seconds:.2f}s par tour."
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
