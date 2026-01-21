#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Test du système de scoring et coaching
Script de validation des calculs
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
import numpy as np

from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
from src.analysis.geometry import (
    calculate_trajectory_geometry, detect_corners, calculate_optimal_trajectory
)
from src.analysis.scoring import calculate_performance_score
from src.analysis.performance_metrics import analyze_corner_performance
from src.analysis.coaching import generate_coaching_advice

# Fichier de test (chemin relatif depuis project_root)
file_path = project_root / "tests" / "data" / "multi_corners.csv"
if not file_path.exists():
    # Fallback: chercher dans différents endroits possibles
    possible_paths = [
        project_root / "tests" / "data" / "multi_corners.csv",
        project_root / "fichier csv fictif" / "multi_corners.csv",
        project_root / "multi_corners.csv",
    ]
    for path in possible_paths:
        if path.exists():
            file_path = path
            break
    else:
        print(f"❌ Fichier CSV non trouvé. Cherché dans : {[str(p) for p in possible_paths]}")
        sys.exit(1)

print("=" * 70)
print("🧪 TEST SYSTÈME SCORING & COACHING")
print("=" * 70)

# Chargement
print("\n📁 [1/5] Chargement fichier...")
result = robust_load_telemetry(file_path)
if not result['success']:
    print(f"❌ Échec : {result['error']}")
    sys.exit(1)

df = result['data']
print(f"✅ {result['metadata']['rows']} lignes chargées")

# Filtrage
print("\n🔧 [2/5] Filtrage GPS...")
df = apply_savgol_filter(df)
print(f"✅ Filtrage terminé (SNR: {df.attrs.get('filtering', {}).get('snr_db', 0):.1f} dB)")

# Géométrie
print("\n📐 [3/5] Calcul géométrie...")
df = calculate_trajectory_geometry(df)
df = detect_corners(df, min_lateral_g=0.08)
df = calculate_optimal_trajectory(df)

corners_meta = df.attrs.get('corners', {})
corner_details = corners_meta.get('corner_details', [])
print(f"✅ {len(corner_details)} virages détectés")

# Scoring
print("\n📊 [4/5] Calcul score de performance...")
score_data = calculate_performance_score(df, corner_details)

print(f"\n🏁 SCORE GLOBAL : {score_data['overall_score']}/100 (Grade {score_data['grade']})")
print(f"\nBreakdown :")
for key, value in score_data['breakdown'].items():
    print(f"  • {key}: {value:.1f}")

print(f"\nDétails :")
for key, value in score_data['details'].items():
    if isinstance(value, list):
        print(f"  • {key}: {', '.join(map(str, value))}")
    else:
        print(f"  • {key}: {value}")

# Analyse par virage
print("\n🎯 [5/5] Analyse détaillée par virage...")
corner_analysis = []
for corner in corner_details[:5]:  # Test sur 5 premiers virages
    analysis = analyze_corner_performance(df, corner)
    corner_analysis.append(analysis)
    
    print(f"\nVirage {analysis['corner_id']} ({analysis['corner_type']}) - Score: {analysis['score']}/100 (Grade {analysis['grade']})")
    metrics = analysis['metrics']
    print(f"  • Vitesse apex: {metrics.get('apex_speed_real', 0):.1f} km/h (optimal: {metrics.get('apex_speed_optimal', 0):.1f} km/h)")
    print(f"  • Efficacité: {metrics.get('speed_efficiency', 0)*100:.1f}%")
    print(f"  • Erreur apex: {metrics.get('apex_distance_error', 0):.2f}m ({metrics.get('apex_direction_error', 'N/A')})")
    print(f"  • G latéral max: {metrics.get('lateral_g_max', 0):.2f}g")
    print(f"  • Temps perdu: {metrics.get('time_lost', 0):.2f}s")

# Coaching
print("\n💡 Génération conseils de coaching...")
coaching_advice = generate_coaching_advice(df, corner_details, score_data, corner_analysis)

print(f"\n🎯 TOP 5 CONSEILS PRIORITAIRES :\n")
for i, advice in enumerate(coaching_advice[:5], 1):
    print(f"{i}. [{advice['category'].upper()}] {advice['message']}")
    print(f"   Impact: {advice['impact_seconds']:.2f}s | Difficulté: {advice['difficulty']}")
    if 'explanation' in advice:
        print(f"   💡 {advice['explanation']}")
    print()

print("=" * 70)
print("✅ TEST TERMINÉ AVEC SUCCÈS !")
print("=" * 70)
