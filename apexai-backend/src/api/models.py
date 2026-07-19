#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - API Models
Modèles Pydantic pour l'API REST
"""

from pydantic import BaseModel, Field, model_validator
from typing import List, Dict, Optional, Any
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
    """URLs des graphiques générés (base64 data URIs)"""
    trajectory_2d: Optional[str] = None
    lap_comparison: Optional[str] = None
    lateral_g_chart: Optional[str] = None
    speed_trace: Optional[str] = None
    corner_performance_matrix: Optional[str] = None
    time_loss_by_corner: Optional[str] = None
    speed_delta_by_corner: Optional[str] = None
    performance_radar: Optional[str] = None
    performance_score_breakdown: Optional[str] = None
    corner_heatmap: Optional[str] = None

    class Config:
        extra = "allow"


class Statistics(BaseModel):
    """Statistiques de l'analyse"""
    processing_time_seconds: float = Field(description="Temps de traitement")
    data_points: int = Field(description="Nombre de points de données")
    best_corners: List[int] = Field(description="Numéros des meilleurs virages")
    worst_corners: List[int] = Field(description="Numéros des virages à travailler")
    avg_apex_distance: float = Field(description="Distance apex moyenne en mètres")
    avg_apex_speed_efficiency: float = Field(description="Efficacité vitesse moyenne")
    laps_analyzed: Optional[int] = Field(default=None, description="Nombre de tours sélectionnés pour l'analyse")
    fastest_lap_number: Optional[int] = Field(default=None, description="Numéro du tour le plus rapide")
    max_speed: Optional[float] = Field(default=None, description="Vitesse maximale atteinte (km/h)")
    max_speed_lap: Optional[int] = Field(default=None, description="Numéro du tour où la vitesse maximale a été atteinte")
    consistency_gap: Optional[float] = Field(default=None, description="Écart moyen entre les tours en secondes")
    improvement_gap: Optional[float] = Field(default=None, description="Gain entre le pire et le meilleur tour en secondes")


class SessionConditions(BaseModel):
    """Conditions de piste renseignées par l'utilisateur"""
    session_name: Optional[str] = Field(default=None, description="Nom optionnel de la session")
    track_condition: str = Field(default="dry", description="dry | damp | wet | rain")
    track_temperature: Optional[float] = Field(default=None, description="Température piste en °C")
    circuit_name: Optional[str] = Field(default=None, description="Nom du circuit extrait du header télémétrie (Venue)")


class TrackFeatures(BaseModel):
    """Signature de piste dérivée de la télémétrie (voir analysis/track_signature.py)"""
    speed_ratio: Optional[str] = Field(default=None, description="sinueux | mixte | rapide")
    rotation: Optional[str] = Field(default=None, description="horaire | anti-horaire")
    hairpins_count: Optional[int] = Field(default=None, description="Virages lents (apex < 45 km/h)")
    fast_corners_count: Optional[int] = Field(default=None, description="Virages rapides (apex > 85 km/h)")
    elevation: Optional[str] = Field(default=None, description="Non dérivable sans canal altitude")
    bumpiness: Optional[str] = Field(default=None, description="Non dérivable sans accéléro vertical")
    corners_total: Optional[int] = Field(default=None, description="Nombre total de virages détectés")
    track_length_m: Optional[float] = Field(default=None, description="Longueur médiane d'un tour en mètres")
    avg_apex_speed_kmh: Optional[float] = Field(default=None, description="Vitesse apex moyenne")


class AnalysisResponse(BaseModel):
    """Réponse complète d'analyse"""
    success: bool = True
    analysis_id: str = Field(description="ID unique de l'analyse")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    corners_detected: int = Field(description="Nombre de virages détectés")
    lap_time: float = Field(description="Temps du tour en secondes (rétrocompat = best_lap_time)")
    best_lap_time: Optional[float] = Field(default=None, description="Meilleur temps parmi les tours analysés")
    lap_times: Optional[List[float]] = Field(default=None, description="Liste ordonnée des temps par tour (tours sélectionnés)")
    
    performance_score: PerformanceScore
    corner_analysis: List[CornerAnalysis] = Field(description="Analyse de chaque virage (max 10)")
    coaching_advice: List[CoachingAdvice] = Field(description="Top 5 conseils")
    
    plots: PlotUrls
    plot_data: Optional[Dict[str, Any]] = Field(default=None, description="Raw data for interactive frontend plotting (Recharts)")
    statistics: Statistics
    session_conditions: Optional[SessionConditions] = Field(default=None, description="Conditions de piste (sec/humide/mouillé/pluie, température)")
    track_features: Optional[TrackFeatures] = Field(default=None, description="Signature de piste dérivée de la télémétrie")


class ErrorResponse(BaseModel):
    """Réponse d'erreur"""
    success: bool = False
    error: str = Field(description="Type d'erreur")
    message: str = Field(description="Message d'erreur")
    details: Optional[Dict] = Field(default=None, description="Détails supplémentaires")


class CircuitCreate(BaseModel):
    name: str
    
    # Alignement strict avec la Track Signature
    speed_ratio: str = Field(..., alias="speedRatio")
    rotation: str
    hairpins_count: int = Field(0, alias="hairpinsCount")
    fast_corners_count: int = Field(0, alias="fastCornersCount")
    elevation: str
    bumpiness: str

    class Config:
        populate_by_name = True


class AdvisorRequest(BaseModel):
    """Requête de recommandations ingénieur (pressions pneus)."""
    tire_model: Optional[str] = Field(default=None, alias="tireModel")
    weather: str = Field(default="sec", description="sec | humide | pluie")
    track_temp: Optional[float] = Field(default=None, alias="trackTemp")
    air_temp: Optional[float] = Field(default=None, alias="airTemp")
    grip: str = Field(default="normal", description="faible | normal | gommée")
    circuit: Optional[Dict[str, Any]] = None
    mode: Optional[str] = Field(default=None, description="warmup | qualif | course")

    class Config:
        populate_by_name = True


class TireSetPayload(BaseModel):
    """Création / mise à jour d'un train de pneus."""
    label: Optional[str] = None
    component_id: Optional[str] = Field(default=None, alias="componentId")
    custom_model: Optional[str] = Field(default=None, alias="customModel")
    state: Optional[str] = Field(default=None, description="neuf | rode | use")
    is_rain: Optional[bool] = Field(default=None, alias="isRain")
    laps_current: Optional[int] = Field(default=None, alias="lapsCurrent")
    laps_life: Optional[int] = Field(default=None, alias="lapsLife")
    active: Optional[bool] = None
    notes: Optional[str] = None

    class Config:
        populate_by_name = True


class KartSetupCreate(BaseModel):
    """Payload for saving a kart setup"""
    id: Optional[str] = None
    setupName: Optional[str] = Field(default="Nouveau Setup", description="Nom du setup")
    weather: Optional[str] = None
    airTemp: Optional[float] = None
    trackTemp: Optional[float] = None
    mode: Optional[str] = None
    circuit: Optional[Dict[str, Any]] = None
    circuit_id: Optional[str] = None
    tireModel: Optional[str] = None
    coldPressureFront: Optional[float] = None
    coldPressureRear: Optional[float] = None
    hotPressureFront: Optional[float] = None
    hotPressureRear: Optional[float] = None
    trackWidthFront: Optional[float] = None
    trackWidthRear: Optional[float] = None
    rideHeightFront: Optional[str] = None
    rideHeightRear: Optional[str] = None
    camber: Optional[str] = None
    caster: Optional[str] = None
    rearAxle: Optional[str] = None
    sprocketFront: Optional[float] = None
    sprocketRear: Optional[float] = None
    carbConfig: Optional[Dict[str, Any]] = None
    driverWeight: Optional[float] = None
    kartWeight: Optional[float] = None
    targetWeight: Optional[float] = None
    ballast: Optional[float] = None
    recommendations: Optional[Dict[str, Any]] = Field(default=None, description="Recommandations figées à la génération")

    @model_validator(mode="before")
    @classmethod
    def empty_str_to_none(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: (None if v == "" else v) for k, v in data.items()}
        return data

    class Config:
        extra = "allow"
