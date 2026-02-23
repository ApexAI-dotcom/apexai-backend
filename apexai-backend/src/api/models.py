#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Models
Modèles Pydantic pour l'API REST
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime


class ScoreBreakdown(BaseModel):
    """Breakdown du score de performance (somme = overall_score, total 100 pts)"""
    apex_precision: float = Field(description="Score précision apex /30")
    trajectory_consistency: float = Field(description="Score régularité /25")
    apex_speed: float = Field(description="Score vitesse apex /25")
    sector_times: float = Field(description="Score temps secteurs /20")


class PerformanceScore(BaseModel):
    """Score de performance global"""
    overall_score: float = Field(description="Score global /100")
    grade: str = Field(description="Grade A+/A/B/C/D")
    breakdown: ScoreBreakdown
    percentile: Optional[int] = Field(default=78, description="Percentile vs autres pilotes")


class CornerAnalysis(BaseModel):
    """Analyse d'un virage"""
    corner_id: int
    corner_number: int
    corner_type: Optional[str] = Field(default="unknown", description="left/right/unknown")
    
    # Vitesse apex (optionnels avec valeurs par défaut)
    apex_speed_real: Optional[float] = Field(default=0.0, description="Vitesse apex réelle (km/h)")
    apex_speed_optimal: Optional[float] = Field(default=0.0, description="Vitesse apex optimale (km/h)")
    speed_efficiency: Optional[float] = Field(default=0.0, description="Efficacité vitesse (0-1)")
    
    # Erreurs apex (optionnels)
    apex_distance_error: Optional[float] = Field(default=0.0, description="Erreur apex en mètres")
    apex_direction_error: Optional[str] = Field(default="center", description="Direction de l'erreur")
    
    # G latéral et temps perdu
    lateral_g_max: Optional[float] = Field(default=0.0, description="G latéral maximum")
    time_lost: Optional[float] = Field(default=0.0, description="Temps perdu en secondes")
    
    # Score du virage
    grade: Optional[str] = Field(default="C", description="Grade A/B/C/D")
    score: Optional[float] = Field(default=50.0, description="Score du virage /100")
    
    class Config:
        extra = "allow"  # Accepter les champs supplémentaires


class CoachingAdvice(BaseModel):
    """Conseil de coaching"""
    priority: int = Field(default=5, description="Priorité (1 = plus impact)")
    category: str = Field(default="global", description="braking/apex/speed/trajectory/global")
    impact_seconds: float = Field(default=0.0, description="Impact en secondes")
    corner: Optional[int] = Field(default=None, description="Numéro du virage (si applicable)")
    message: str = Field(default="", description="Message du conseil")
    explanation: str = Field(default="", description="Explication détaillée")
    difficulty: str = Field(default="moyen", description="facile/moyen/difficile")
    
    class Config:
        extra = "allow"  # Accepter les champs supplémentaires


class PlotUrls(BaseModel):
    """URLs des graphiques générés"""
    trajectory_2d: Optional[str] = None
    speed_heatmap: Optional[str] = None
    lateral_g_chart: Optional[str] = None
    speed_trace: Optional[str] = None
    throttle_brake: Optional[str] = None
    sector_times: Optional[str] = None
    apex_precision: Optional[str] = None
    performance_radar: Optional[str] = None
    performance_score_breakdown: Optional[str] = None
    corner_heatmap: Optional[str] = None
    
    class Config:
        extra = "allow"  # Accepter tous les plots retournés


class Statistics(BaseModel):
    """Statistiques de l'analyse"""
    processing_time_seconds: float = Field(description="Temps de traitement")
    data_points: int = Field(description="Nombre de points de données")
    best_corners: List[int] = Field(description="Numéros des meilleurs virages")
    worst_corners: List[int] = Field(description="Numéros des virages à travailler")
    avg_apex_distance: float = Field(description="Distance apex moyenne en mètres")
    avg_apex_speed_efficiency: float = Field(description="Efficacité vitesse moyenne")
    laps_analyzed: Optional[int] = Field(default=None, description="Nombre de tours sélectionnés pour l'analyse")


class SessionConditions(BaseModel):
    """Conditions de piste renseignées par l'utilisateur"""
    track_condition: str = Field(default="dry", description="dry | damp | wet | rain")
    track_temperature: Optional[float] = Field(default=None, description="Température piste en °C")


class AnalysisResponse(BaseModel):
    """Réponse complète d'analyse"""
    success: bool = True
    analysis_id: str = Field(description="ID unique de l'analyse")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    corners_detected: int = Field(description="Nombre de virages détectés")
    lap_time: float = Field(description="Temps du tour en secondes")
    
    performance_score: PerformanceScore
    corner_analysis: List[CornerAnalysis] = Field(description="Analyse de chaque virage (max 10)")
    coaching_advice: List[CoachingAdvice] = Field(description="Top 5 conseils")
    
    plots: PlotUrls
    statistics: Statistics
    session_conditions: Optional[SessionConditions] = Field(default=None, description="Conditions de piste (sec/humide/mouillé/pluie, température)")


class ErrorResponse(BaseModel):
    """Réponse d'erreur"""
    success: bool = False
    error: str = Field(description="Type d'erreur")
    message: str = Field(description="Message d'erreur")
    details: Optional[Dict] = Field(default=None, description="Détails supplémentaires")
