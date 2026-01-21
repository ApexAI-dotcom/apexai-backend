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
            
            if braking_delta > 0:  # Freine trop tôt
                message = f"Virage {corner_id} : Tu freines {braking_delta:.1f}m trop tôt (-{impact_seconds:.2f}s perdu)"
                explanation = f"Point de freinage actuel : {metrics.get('braking_point_distance', 0):.1f}m avant apex. Optimal : {metrics.get('braking_point_optimal', 0):.1f}m. En retardant le freinage, tu maintiens plus de vitesse."
                difficulty = "facile"
                visual_cue = f"Repère un point {braking_delta:.0f}m plus proche de l'apex pour déclencher le freinage"
            
            else:  # Freine trop tard
                message = f"Virage {corner_id} : Tu freines {abs(braking_delta):.1f}m trop tard (-{impact_seconds:.2f}s perdu)"
                explanation = f"Point de freinage actuel : {metrics.get('braking_point_distance', 0):.1f}m avant apex. Optimal : {metrics.get('braking_point_optimal', 0):.1f}m. Anticipe le freinage pour aborder le virage plus sereinement."
                difficulty = "moyen"
                visual_cue = f"Repère un point {abs(braking_delta):.0f}m plus loin de l'apex pour commencer à freiner"
            
            advice.append({
                'priority': len(advice) + 1,
                'category': 'braking',
                'impact_seconds': round(impact_seconds, 2),
                'corner': corner_id,
                'message': message,
                'explanation': explanation,
                'difficulty': difficulty,
                'visual_cue': visual_cue
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
            
            if direction:
                if direction in ["left", "right"]:
                    message = f"Virage {corner_id} : Apex décalé de {apex_error:.1f}m à {direction}"
                else:
                    message = f"Virage {corner_id} : Apex décalé de {apex_error:.1f}m ({direction})"
                
                explanation = f"Ligne actuelle clippe l'intérieur avec une erreur de {apex_error:.1f}m. Vise {apex_error:.1f}m plus {'à droite' if direction == 'left' else 'à gauche'} pour optimiser la sortie."
            else:
                message = f"Virage {corner_id} : Apex décalé de {apex_error:.1f}m"
                explanation = f"Position de l'apex non optimale. Ajuste ta trajectoire pour clipper l'intérieur plus précisément."
            
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
            message = f"Virage {corner_id} : Vitesse apex {speed_real:.1f} km/h vs optimal {speed_optimal:.1f} km/h ({efficiency_pct:.0f}% efficacité)"
            explanation = f"Vitesse actuelle à l'apex : {speed_real:.1f} km/h. Optimal : {speed_optimal:.1f} km/h. Tu peux maintenir {speed_delta:.1f} km/h de plus en confiant davantage au grip."
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
    """Génère conseils globaux."""
    advice = []
    
    try:
        breakdown = score_data.get('breakdown', {})
        
        # Conseils par secteur
        sector_scores = {}
        for corner in corner_analysis:
            corner_id = corner.get('corner_id', 0)
            # Approximatif : diviser virages en 3 tiers
            if corner_id <= len(corner_analysis) / 3:
                sector = 1
            elif corner_id <= 2 * len(corner_analysis) / 3:
                sector = 2
            else:
                sector = 3
            
            if sector not in sector_scores:
                sector_scores[sector] = []
            sector_scores[sector].append(corner.get('score', 70))
        
        for sector, scores in sector_scores.items():
            avg_score = sum(scores) / len(scores) if scores else 70
            
            if avg_score < 70:
                worst_corners = [c.get('corner_id') for c in corner_analysis 
                               if c.get('score', 70) < 70][:3]
                impact_seconds = (70 - avg_score) * 0.05
                message = f"Secteur {sector} : {avg_score:.0f}% sous l'optimal, focus virages {', '.join(map(str, worst_corners))}"
                explanation = f"Score moyen secteur {sector} : {avg_score:.0f}/100. Concentre-toi sur les virages {', '.join(map(str, worst_corners))} pour améliorer."
                
                advice.append({
                    'priority': len(advice) + 1,
                    'category': 'global',
                    'impact_seconds': round(impact_seconds, 2),
                    'corner': None,
                    'message': message,
                    'explanation': explanation,
                    'difficulty': 'moyen'
                })
        
        # Constance générale
        consistency_score = breakdown.get('trajectory_consistency', 10.0)
        if consistency_score < 15.0:
            # Détecter micro-corrections
            if 'heading' in df.columns:
                heading = df['heading'].diff().abs()
                corrections = (heading > 5.0).sum()
                
                if corrections > 10:
                    impact_seconds = (15.0 - consistency_score) * 0.02
                    message = f"Constance générale : {corrections} micro-corrections détectées, travail smoothness"
                    explanation = f"{corrections} corrections de trajectoire détectées (>5°). Travaille la fluidité pour réduire les corrections et gagner en temps."
                    
                    advice.append({
                        'priority': len(advice) + 1,
                        'category': 'global',
                        'impact_seconds': round(impact_seconds, 2),
                        'corner': None,
                        'message': message,
                        'explanation': explanation,
                        'difficulty': 'moyen'
                    })
        
        # Point fort
        details = score_data.get('details', {})
        best_corners = details.get('best_corners', [])
        
        if best_corners:
            impact_seconds = 0.0  # Pas d'impact, juste encouragement
            message = f"Point fort : Virages {', '.join(map(str, best_corners))}, reproduis cette approche ailleurs"
            explanation = f"Tes meilleurs virages : {', '.join(map(str, best_corners))}. Analyse ce que tu fais différemment ici et applique-le aux autres virages."
            
            advice.append({
                'priority': len(advice) + 1,
                'category': 'global',
                'impact_seconds': round(impact_seconds, 2),
                'corner': None,
                'message': message,
                'explanation': explanation,
                'difficulty': 'facile'
            })
    
    except Exception as e:
        warnings.warn(f"Error generating global advice: {str(e)}")
    
    return advice
