#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Visualization (Karting Pro)
Création de 8 graphiques style F1 AWS pour analyse professionnelle
"""

# Backend headless OBLIGATOIRE pour Railway/Render (pas de display)
import matplotlib
matplotlib.use("Agg")

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from typing import Dict, Optional
import warnings
import tempfile
import os

# Constantes de style
COLOR_BLUE = '#2E86DE'
COLOR_GREEN = '#10AC84'
COLOR_RED = '#EE5A6F'
COLOR_ORANGE = '#F79F1F'
GRID_COLOR = '#E8E8E8'
FIG_SIZE = (12, 8)
DPI = 150


def _calculate_scores(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calcule les 5 scores (0-100) pour le radar chart.
    
    Args:
        df: DataFrame avec colonnes nécessaires
    
    Returns:
        Dictionnaire avec scores : apex_precision, speed_efficiency, consistency, braking, racing_line
    """
    scores = {
        'apex_precision': 75.0,
        'speed_efficiency': 80.0,
        'consistency': 85.0,
        'braking': 70.0,
        'racing_line': 75.0
    }
    
    try:
        # 1. Apex Precision (si corner_details disponible)
        if 'corners' in df.attrs and 'corner_details' in df.attrs['corners']:
            corner_details = df.attrs['corners']['corner_details']
            if corner_details:
                # Calculer score basé sur la précision (moins de déviation = mieux)
                # Score de base, sera amélioré si apex_deviation disponible
                scores['apex_precision'] = 85.0
        
        # 2. Speed Efficiency
        if 'corners' in df.attrs and 'corner_details' in df.attrs['corners']:
            corner_details = df.attrs['corners']['corner_details']
            if corner_details:
                efficiencies = [c.get('speed_efficiency_pct', 80.0) for c in corner_details 
                               if 'speed_efficiency_pct' in c]
                if efficiencies:
                    scores['speed_efficiency'] = float(np.mean(efficiencies))
        
        # 3. Consistency (si multi-tours, sinon valeur par défaut)
        if 'time' in df.columns and len(df) > 10:
            # Simplifié : score fixe pour single-lap
            scores['consistency'] = 85.0
        
        # 4. Braking (score basé sur ratio throttle/brake)
        if 'throttle' in df.columns and 'brake' in df.columns:
            throttle = pd.to_numeric(df['throttle'], errors='coerce').fillna(0).values
            brake = pd.to_numeric(df['brake'], errors='coerce').fillna(0).values
            
            # Score = % du temps où brake est utilisé de manière optimale
            brake_ratio = np.sum(brake > 20) / len(brake) if len(brake) > 0 else 0.5
            scores['braking'] = float(min(100, brake_ratio * 100 * 1.5))
        
        # 5. Racing Line (basé sur variance curvature)
        if 'curvature' in df.columns:
            curvature = pd.to_numeric(df['curvature'], errors='coerce').fillna(0).values
            curvature_variance = np.var(np.abs(curvature))
            # Moins de variance = ligne plus stable = meilleur score
            scores['racing_line'] = float(max(50, 100 - curvature_variance * 10000))
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur calcul scores : {str(e)}")
    
    return scores


def plot_trajectory_2d(df: pd.DataFrame, save_path: str) -> bool:
    """
    Graphique 1 : Trajectoire GPS 2D avec apex marqués.
    """
    try:
        required_cols = ['longitude_smooth', 'latitude_smooth', 'speed']
        if not all(col in df.columns for col in required_cols):
            warnings.warn("⚠️ Colonnes manquantes pour trajectory_2d")
            return False
        
        lon = pd.to_numeric(df['longitude_smooth'], errors='coerce').values
        lat = pd.to_numeric(df['latitude_smooth'], errors='coerce').values
        speed = pd.to_numeric(df['speed'], errors='coerce').values
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        
        # Trajectoire brute (gris fine)
        ax.plot(lon, lat, color='gray', linewidth=0.5, alpha=0.3, label='Trajectoire brute')
        
        # Trajectoire colorée par vitesse
        scatter = ax.scatter(lon, lat, c=speed, cmap='jet', s=50, alpha=0.8, 
                           vmin=0, vmax=np.nanmax(speed), edgecolors='none')
        ax.plot(lon, lat, color='black', linewidth=2, alpha=0.3)
        
            # Marqueurs apex
        if 'is_apex' in df.columns and 'corner_id' in df.columns:
            apex_mask = df['is_apex'] == True
            if apex_mask.any():
                apex_lon = lon[apex_mask.values]
                apex_lat = lat[apex_mask.values]
                apex_ids = df.loc[df['is_apex'], 'corner_id'].values
                apex_speeds = speed[apex_mask.values]
                
                # Apex réels (rouges)
                ax.scatter(apex_lon, apex_lat, marker='*', s=200, color='red', 
                          edgecolors='black', linewidths=1, zorder=10, label='Apex réel')
                
                # Apex idéaux (verts) - si disponibles
                try:
                    from src.analysis.scoring import calculate_optimal_apex_position
                    
                    if 'corners' in df.attrs and 'corner_details' in df.attrs['corners']:
                        corner_details = df.attrs['corners']['corner_details']
                        ideal_apex_lon = []
                        ideal_apex_lat = []
                        
                        for corner in corner_details:
                            corner_mask = df['corner_id'] == corner['id']
                            corner_indices = df[corner_mask].index.tolist()
                            
                            if len(corner_indices) >= 3:
                                optimal = calculate_optimal_apex_position(df, corner_indices)
                                if optimal:
                                    ideal_apex_lat.append(optimal['latitude'])
                                    ideal_apex_lon.append(optimal['longitude'])
                        
                        if ideal_apex_lon:
                            ax.scatter(ideal_apex_lon, ideal_apex_lat, marker='x', s=150, 
                                     color='green', linewidths=2, zorder=10, label='Apex idéal')
                            
                            # Lignes pointillées entre apex réel et idéal
                            for i, (real_idx, real_x, real_y) in enumerate(zip(apex_ids, apex_lon, apex_lat)):
                                for j, (ideal_x, ideal_y) in enumerate(zip(ideal_apex_lon, ideal_apex_lat)):
                                    # Vérifier si même virage (approximation)
                                    if abs(real_x - ideal_x) < 0.001 and abs(real_y - ideal_y) < 0.001:
                                        continue
                                    # Ligne si proche (même virage probablement)
                                    dist = np.sqrt((real_x - ideal_x)**2 + (real_y - ideal_y)**2)
                                    if dist < 0.001:  # Threshold pour même virage
                                        ax.plot([real_x, ideal_x], [real_y, ideal_y], 
                                              'k--', alpha=0.3, linewidth=1, zorder=9)
                except Exception:
                    pass
                
                # Annotations
                for i, (x, y, cid, spd) in enumerate(zip(apex_lon, apex_lat, apex_ids, apex_speeds)):
                    if pd.notna(spd) and pd.notna(cid):
                        ax.annotate(f'V{int(cid)}\n{spd:.0f}km/h', 
                                  xy=(x, y), xytext=(5, 10), 
                                  textcoords='offset points', fontsize=9,
                                  bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
        
        # Point départ et arrivée
        if len(lon) > 0:
            ax.scatter(lon[0], lat[0], s=150, color=COLOR_GREEN, marker='o', 
                      edgecolors='black', linewidths=2, zorder=10, label='Départ')
            ax.scatter(lon[-1], lat[-1], s=150, color='black', marker='s', 
                      edgecolors='white', linewidths=2, zorder=10, label='Arrivée')
        
        # Colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Vitesse (km/h)', fontsize=12)
        
        ax.set_aspect('equal')
        ax.grid(True, color=GRID_COLOR, alpha=0.5, linestyle='--')
        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        ax.set_title('Trajectoire GPS - Circuit Complet', fontsize=16, fontweight='bold')
        ax.legend(loc='best', frameon=False, fontsize=10)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        
        return True
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur plot_trajectory_2d : {str(e)}")
        return False


def plot_speed_heatmap(df: pd.DataFrame, save_path: str) -> bool:
    """
    Graphique 2 : Heatmap de vitesse sur la trajectoire (style F1).
    """
    try:
        required_cols = ['longitude_smooth', 'latitude_smooth', 'speed']
        if not all(col in df.columns for col in required_cols):
            warnings.warn("⚠️ Colonnes manquantes pour speed_heatmap")
            return False
        
        lon = pd.to_numeric(df['longitude_smooth'], errors='coerce').values
        lat = pd.to_numeric(df['latitude_smooth'], errors='coerce').values
        speed = pd.to_numeric(df['speed'], errors='coerce').values
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        
        # Scatter plot coloré par vitesse
        scatter = ax.scatter(lon, lat, c=speed, cmap='RdYlGn_r', s=50, alpha=0.8,
                           vmin=0, vmax=np.nanmax(speed))
        
        # Contours apex (cercles noirs pointillés)
        if 'is_apex' in df.columns:
            apex_mask = df['is_apex'] == True
            if apex_mask.any():
                apex_lon = lon[apex_mask.values]
                apex_lat = lat[apex_mask.values]
                for x, y in zip(apex_lon, apex_lat):
                    circle = plt.Circle((x, y), 0.0001, fill=False, edgecolor='black', 
                                       linestyle='--', linewidth=1.5)
                    ax.add_patch(circle)
        
        # Colorbar avec labels
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Vitesse (km/h)', fontsize=12)
        cbar.ax.text(0.5, 0.05, '< 40 km/h', transform=cbar.ax.transAxes, 
                    ha='center', fontsize=9, color='red')
        cbar.ax.text(0.5, 0.95, '> 80 km/h', transform=cbar.ax.transAxes, 
                    ha='center', fontsize=9, color='green')
        
        ax.set_aspect('equal')
        ax.grid(True, color=GRID_COLOR, alpha=0.5, linestyle='--')
        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        ax.set_title('Heatmap Vitesse - Zones Critiques', fontsize=16, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        
        return True
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur plot_speed_heatmap : {str(e)}")
        return False


def plot_lateral_g_chart(df: pd.DataFrame, save_path: str) -> bool:
    """
    Graphique 3 : G latéral par virage avec limites théoriques.
    """
    try:
        if 'corners' not in df.attrs or 'corner_details' not in df.attrs['corners']:
            warnings.warn("⚠️ Pas de données virages pour lateral_g_chart")
            return False
        
        corner_details = df.attrs['corners']['corner_details']
        if not corner_details:
            return False
        
        corner_ids = [c['id'] for c in corner_details]
        max_lateral_g = [c['max_lateral_g'] for c in corner_details]
        
        # Couleurs selon G
        colors = []
        for g in max_lateral_g:
            if g > 2.0:
                colors.append(COLOR_RED)
            elif g > 1.5:
                colors.append(COLOR_ORANGE)
            else:
                colors.append(COLOR_GREEN)
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        
        bars = ax.bar(corner_ids, max_lateral_g, color=colors, alpha=0.7, edgecolor='black', linewidth=1)
        
        # Lignes de référence
        ax.axhline(y=2.5, color=COLOR_RED, linestyle='--', linewidth=2, label='Limite sécurité (2.5g)')
        ax.axhline(y=1.8, color=COLOR_GREEN, linestyle='--', linewidth=2, label='Target optimal (1.8g)')
        
        # Annotations
        for i, (cid, g) in enumerate(zip(corner_ids, max_lateral_g)):
            ax.text(cid, g + 0.05, f'{g:.2f}g', ha='center', va='bottom', fontsize=9)
        
        ax.set_xlabel('Virage', fontsize=12)
        ax.set_ylabel('G latéral (g)', fontsize=12)
        ax.set_title('Accélération Latérale - Par Virage', fontsize=16, fontweight='bold')
        ax.grid(True, axis='y', color=GRID_COLOR, alpha=0.5, linestyle='--')
        ax.legend(loc='best', frameon=False, fontsize=10)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        
        return True
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur plot_lateral_g_chart : {str(e)}")
        return False


def plot_speed_trace(df: pd.DataFrame, save_path: str) -> bool:
    """
    Graphique 4 : Vitesse le long du tour avec zones virages colorées.
    """
    try:
        required_cols = ['cumulative_distance', 'speed']
        if not all(col in df.columns for col in required_cols):
            warnings.warn("⚠️ Colonnes manquantes pour speed_trace")
            return False
        
        dist = pd.to_numeric(df['cumulative_distance'], errors='coerce').values
        speed = pd.to_numeric(df['speed'], errors='coerce').values
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        
        # Background shading zones virages
        if 'is_corner' in df.columns:
            corner_mask = df['is_corner'] == True
            if corner_mask.any():
                # Créer régions de virages
                corner_regions = []
                in_corner = False
                start_idx = 0
                for i, is_corner in enumerate(corner_mask):
                    if is_corner and not in_corner:
                        start_idx = i
                        in_corner = True
                    elif not is_corner and in_corner:
                        if start_idx < len(dist) and i < len(dist):
                            corner_regions.append((dist[start_idx], dist[i]))
                        in_corner = False
                if in_corner and start_idx < len(dist):
                    corner_regions.append((dist[start_idx], dist[-1]))
                
                for start_d, end_d in corner_regions:
                    ax.axvspan(start_d, end_d, alpha=0.2, color=COLOR_RED)
        
        # Ligne de vitesse
        ax.plot(dist, speed, color=COLOR_BLUE, linewidth=2.5, label='Vitesse')
        
        # Ligne vitesse moyenne
        avg_speed = np.nanmean(speed)
        ax.axhline(y=avg_speed, color='black', linestyle='--', linewidth=1.5, 
                  alpha=0.7, label=f'Vitesse moyenne ({avg_speed:.1f} km/h)')
        
        # Marqueurs apex
        if 'is_apex' in df.columns and 'cumulative_distance' in df.columns:
            apex_mask = df['is_apex'] == True
            if apex_mask.any():
                apex_dist = df.loc[df['is_apex'], 'cumulative_distance'].values
                apex_speed = speed[apex_mask.values]
                ax.scatter(apex_dist, apex_speed, marker='v', s=100, color='black', 
                          zorder=10, label='Apex', edgecolors='white', linewidths=1)
        
        # Annotations secteurs
        if len(dist) > 0:
            total_dist = dist[-1]
            ax.axvline(x=total_dist/3, color='gray', linestyle=':', alpha=0.5)
            ax.axvline(x=2*total_dist/3, color='gray', linestyle=':', alpha=0.5)
            ax.text(total_dist/6, ax.get_ylim()[1]*0.95, 'S1', ha='center', fontsize=11, 
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            ax.text(total_dist/2, ax.get_ylim()[1]*0.95, 'S2', ha='center', fontsize=11,
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            ax.text(5*total_dist/6, ax.get_ylim()[1]*0.95, 'S3', ha='center', fontsize=11,
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        ax.set_xlabel('Distance (m)', fontsize=12)
        ax.set_ylabel('Vitesse (km/h)', fontsize=12)
        ax.set_title('Trace de Vitesse - Tour Complet', fontsize=16, fontweight='bold')
        ax.grid(True, color=GRID_COLOR, alpha=0.5, linestyle='--')
        ax.legend(loc='best', frameon=False, fontsize=10)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        
        return True
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur plot_speed_trace : {str(e)}")
        return False


def plot_throttle_brake(df: pd.DataFrame, save_path: str) -> bool:
    """
    Graphique 5 : Overlay throttle/brake le long du tour.
    """
    try:
        required_cols = ['cumulative_distance']
        if not all(col in df.columns for col in required_cols):
            warnings.warn("⚠️ Colonnes manquantes pour throttle_brake")
            return False
        
        if 'throttle' not in df.columns or 'brake' not in df.columns:
            warnings.warn("⚠️ Colonnes throttle/brake manquantes")
            return False
        
        dist = pd.to_numeric(df['cumulative_distance'], errors='coerce').values
        throttle = pd.to_numeric(df['throttle'], errors='coerce').fillna(0).values
        brake = pd.to_numeric(df['brake'], errors='coerce').fillna(0).values
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        
        # Throttle (vert)
        ax.plot(dist, throttle, color=COLOR_GREEN, linewidth=2, label='Accélérateur')
        ax.fill_between(dist, 0, throttle, color=COLOR_GREEN, alpha=0.3)
        
        # Brake (rouge)
        ax2 = ax.twinx()
        ax2.plot(dist, brake, color=COLOR_RED, linewidth=2, label='Frein')
        ax2.fill_between(dist, 0, brake, color=COLOR_RED, alpha=0.3)
        
        # Grille verticale aux apex
        if 'is_apex' in df.columns and 'cumulative_distance' in df.columns:
            apex_mask = df['is_apex'] == True
            if apex_mask.any():
                apex_dist = df.loc[df['is_apex'], 'cumulative_distance'].values
                for ad in apex_dist:
                    ax.axvline(x=ad, color='gray', linestyle=':', alpha=0.3)
        
        ax.set_xlabel('Distance (m)', fontsize=12)
        ax.set_ylabel('Throttle (%)', fontsize=12, color=COLOR_GREEN)
        ax2.set_ylabel('Brake (%)', fontsize=12, color=COLOR_RED)
        ax.set_title('Throttle & Brake - Application', fontsize=16, fontweight='bold')
        ax.grid(True, color=GRID_COLOR, alpha=0.5, linestyle='--')
        
        # Légendes combinées
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='best', frameon=False, fontsize=10)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        
        return True
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur plot_throttle_brake : {str(e)}")
        return False


def plot_sector_times(df: pd.DataFrame, save_path: str) -> bool:
    """
    Graphique 6 : Comparaison temps secteurs.
    """
    try:
        required_cols = ['cumulative_distance', 'time']
        if not all(col in df.columns for col in required_cols):
            warnings.warn("⚠️ Colonnes manquantes pour sector_times")
            return False
        
        dist = pd.to_numeric(df['cumulative_distance'], errors='coerce').values
        time = pd.to_numeric(df['time'], errors='coerce').values
        
        if len(dist) == 0 or len(time) == 0:
            return False
        
        total_dist = dist[-1]
        total_time = time[-1] - time[0]
        
        # Diviser en 3 secteurs
        s1_end = total_dist / 3
        s2_end = 2 * total_dist / 3
        
        # Calculer temps par secteur
        s1_idx = np.argmin(np.abs(dist - s1_end))
        s2_idx = np.argmin(np.abs(dist - s2_end))
        
        s1_time = time[s1_idx] - time[0]
        s2_time = time[s2_idx] - time[s1_idx]
        s3_time = time[-1] - time[s2_idx]
        
        sector_times = [s1_time, s2_time, s3_time]
        optimal_times = [t * 0.95 for t in sector_times]  # -5% pour démo
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        
        x = np.arange(3)
        width = 0.35
        
        bars1 = ax.bar(x - width/2, sector_times, width, label='Votre temps', 
                      color=COLOR_BLUE, alpha=0.8)
        bars2 = ax.bar(x + width/2, optimal_times, width, label='Temps optimal', 
                      color=COLOR_GREEN, alpha=0.5)
        
        # Annotations delta
        for i, (t, opt) in enumerate(zip(sector_times, optimal_times)):
            delta = t - opt
            ax.text(i, max(t, opt) + total_time*0.02, f'{delta:+.2f}s', 
                   ha='center', va='bottom', fontsize=9)
        
        ax.set_xlabel('Secteur', fontsize=12)
        ax.set_ylabel('Temps (s)', fontsize=12)
        ax.set_title('Analyse Secteurs - Temps Comparés', fontsize=16, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(['S1', 'S2', 'S3'])
        ax.grid(True, axis='y', color=GRID_COLOR, alpha=0.5, linestyle='--')
        ax.legend(loc='best', frameon=False, fontsize=10)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        
        return True
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur plot_sector_times : {str(e)}")
        return False


def plot_apex_precision(df: pd.DataFrame, save_path: str) -> bool:
    """
    Graphique 7 : Distance apex réel vs idéal par virage.
    """
    try:
        # Note : apex_deviation_m n'est plus dans corner_details de geometry.py
        # On va calculer une approximation ou utiliser une métrique alternative
        
        if 'corners' not in df.attrs or 'corner_details' not in df.attrs['corners']:
            warnings.warn("⚠️ Pas de données virages pour apex_precision")
            return False
        
        corner_details = df.attrs['corners']['corner_details']
        if not corner_details:
            return False
        
        # Calculer écart basé sur optimal vs réel si disponible
        corner_ids = [c['id'] for c in corner_details]
        
        # Approximation : utiliser différence vitesse apex vs optimal
        if 'optimal_apex_speed_kmh' in corner_details[0]:
            deviations = []
            for c in corner_details:
                if 'optimal_apex_speed_kmh' in c and 'apex_speed_kmh' in c:
                    opt_speed = c['optimal_apex_speed_kmh']
                    real_speed = c['apex_speed_kmh']
                    # Convertir différence vitesse en distance approximative
                    # 1 km/h ≈ 0.5m à l'apex (approximation)
                    deviation = abs(real_speed - opt_speed) * 0.1  # Métrique approximative
                    deviations.append(deviation)
                else:
                    deviations.append(0.0)
        else:
            # Fallback : utiliser 0 pour tous
            deviations = [0.0] * len(corner_ids)
        
        # Couleurs selon écart
        colors = []
        for d in deviations:
            if d < 1.0:
                colors.append(COLOR_GREEN)
            elif d < 2.0:
                colors.append(COLOR_ORANGE)
            else:
                colors.append(COLOR_RED)
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        
        bars = ax.barh(corner_ids, deviations, color=colors, alpha=0.7, edgecolor='black', linewidth=1)
        
        # Lignes de référence
        ax.axvline(x=0.5, color=COLOR_GREEN, linestyle='--', linewidth=2, label='Excellent (< 0.5m)')
        ax.axvline(x=1.5, color=COLOR_ORANGE, linestyle='--', linewidth=2, label='Acceptable (< 1.5m)')
        
        # Annotations
        for i, (cid, dev) in enumerate(zip(corner_ids, deviations)):
            ax.text(dev + 0.05, cid, f'{dev:.2f}m', va='center', fontsize=9)
        
        ax.set_xlabel('Écart (m)', fontsize=12)
        ax.set_ylabel('Virage', fontsize=12)
        ax.set_title('Précision Apex - Écart Optimal vs Réel', fontsize=16, fontweight='bold')
        ax.grid(True, axis='x', color=GRID_COLOR, alpha=0.5, linestyle='--')
        ax.legend(loc='best', frameon=False, fontsize=10)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        
        return True
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur plot_apex_precision : {str(e)}")
        return False


def plot_performance_radar(df: pd.DataFrame, save_path: str) -> bool:
    """
    Graphique 8 : Radar chart du score par catégorie (style AWS F1).
    """
    try:
        scores = _calculate_scores(df)
        
        categories = ['Apex\nPrecision', 'Speed\nEfficiency', 'Consistency', 
                     'Braking', 'Racing\nLine']
        values = [
            scores['apex_precision'],
            scores['speed_efficiency'],
            scores['consistency'],
            scores['braking'],
            scores['racing_line']
        ]
        
        # Angles pour radar chart
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        values += values[:1]  # Fermer le cercle
        angles += angles[:1]
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI, subplot_kw=dict(projection='polar'))
        
        # Grille circulaire
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=9)
        ax.grid(True, color=GRID_COLOR, alpha=0.5, linestyle='--')
        
        # Plot polygon
        ax.plot(angles, values, 'o-', linewidth=2.5, color=COLOR_BLUE, label='Score')
        ax.fill(angles, values, alpha=0.3, color=COLOR_BLUE)
        
        # Axes et labels
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=11)
        
        # Valeurs aux coins
        for angle, value, category in zip(angles[:-1], values[:-1], categories):
            ax.text(angle, value + 5, f'{value:.0f}', ha='center', va='bottom', 
                   fontsize=10, fontweight='bold')
        
        ax.set_title('Performance Radar - Score Global', fontsize=16, fontweight='bold', pad=20)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        
        return True
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur plot_performance_radar : {str(e)}")
        return False


def plot_performance_score_breakdown(df: pd.DataFrame, save_path: str) -> bool:
    """
    Graphique : Radar/pentagone avec breakdown du score de performance.
    """
    try:
        if 'corners' not in df.attrs or 'corner_details' not in df.attrs['corners']:
            warnings.warn("⚠️ Pas de données score pour performance_score_breakdown")
            return False
        
        # Importer scoring
        from src.analysis.scoring import calculate_performance_score
        
        corner_details = df.attrs['corners']['corner_details']
        score_data = calculate_performance_score(df, corner_details)
        
        breakdown = score_data.get('breakdown', {})
        overall_score = score_data.get('overall_score', 70.0)
        grade = score_data.get('grade', 'B')
        
        categories = ['Précision\nApex', 'Régularité\nTrajectoire', 
                     'Vitesse\nApex', 'Temps\nSecteur']
        values = [
            breakdown.get('apex_precision', 15.0),
            breakdown.get('trajectory_consistency', 10.0),
            breakdown.get('apex_speed', 12.5),
            breakdown.get('sector_times', 12.5)
        ]
        
        # Normaliser à 100% pour le radar
        max_scores = [30.0, 20.0, 25.0, 25.0]
        values_normalized = [v / m * 100 for v, m in zip(values, max_scores)]
        values_normalized += values_normalized[:1]  # Fermer le cercle
        
        # Angles pour radar chart
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI, subplot_kw=dict(projection='polar'))
        
        # Grille circulaire
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=9)
        ax.grid(True, color=GRID_COLOR, alpha=0.5, linestyle='--')
        
        # Couleurs selon score
        if overall_score >= 80:
            color = COLOR_GREEN
        elif overall_score >= 60:
            color = COLOR_ORANGE
        else:
            color = COLOR_RED
        
        # Plot polygon
        ax.plot(angles, values_normalized, 'o-', linewidth=2.5, color=color, label='Score')
        ax.fill(angles, values_normalized, alpha=0.3, color=color)
        
        # Axes et labels
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=11)
        
        # Score global au centre
        ax.text(0, 0, f'{overall_score:.0f}/100', ha='center', va='center', 
               fontsize=24, fontweight='bold')
        ax.text(0, -25, f'Grade {grade}', ha='center', va='center', 
               fontsize=14, fontweight='bold')
        
        # Valeurs aux coins
        for angle, value, max_score in zip(angles[:-1], values, max_scores):
            ax.text(angle, value / max_score * 100 + 5, f'{value:.1f}/{max_score:.0f}', 
                   ha='center', va='bottom', fontsize=9)
        
        ax.set_title('Score de Performance - Breakdown', fontsize=16, fontweight='bold', pad=20)
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        
        return True
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur plot_performance_score_breakdown : {str(e)}")
        return False


def plot_corner_heatmap(df: pd.DataFrame, save_path: str) -> bool:
    """
    Graphique : Carte du circuit avec virages colorés selon performance.
    """
    try:
        required_cols = ['longitude_smooth', 'latitude_smooth', 'corner_id']
        if not all(col in df.columns for col in required_cols):
            warnings.warn("⚠️ Colonnes manquantes pour corner_heatmap")
            return False
        
        if 'corners' not in df.attrs or 'corner_details' not in df.attrs['corners']:
            warnings.warn("⚠️ Pas de données virages pour corner_heatmap")
            return False
        
        # Importer performance_metrics
        from src.analysis.performance_metrics import analyze_corner_performance
        
        corner_details = df.attrs['corners']['corner_details']
        
        # Analyser chaque virage
        corner_performances = {}
        for corner in corner_details:
            analysis = analyze_corner_performance(df, corner)
            corner_performances[corner['id']] = analysis
        
        lon = pd.to_numeric(df['longitude_smooth'], errors='coerce').values
        lat = pd.to_numeric(df['latitude_smooth'], errors='coerce').values
        corner_id = df['corner_id'].values
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        
        # Tracer trajectoire de base
        ax.plot(lon, lat, color='gray', linewidth=1, alpha=0.3, zorder=1)
        
        # Colorer selon performance
        for cid in np.unique(corner_id):
            if cid == 0:  # Ligne droite
                continue
            
            corner_mask = corner_id == cid
            if not corner_mask.any():
                continue
            
            corner_lon = lon[corner_mask]
            corner_lat = lat[corner_mask]
            
            if cid in corner_performances:
                score = corner_performances[cid].get('score', 70)
                
                # Couleur selon score
                if score >= 85:
                    color = COLOR_GREEN
                elif score >= 70:
                    color = COLOR_ORANGE
                else:
                    color = COLOR_RED
            else:
                color = 'gray'
            
            ax.plot(corner_lon, corner_lat, color=color, linewidth=3, zorder=2)
        
        # Annoter numéros de virages
        for corner in corner_details:
            try:
                apex_idx = corner.get('apex_index')
                if apex_idx is not None and apex_idx < len(df):
                    apex_lon = df.iloc[apex_idx]['longitude_smooth']
                    apex_lat = df.iloc[apex_idx]['latitude_smooth']
                    
                    if pd.notna(apex_lon) and pd.notna(apex_lat):
                        if corner['id'] in corner_performances:
                            score = corner_performances[corner['id']].get('score', 70)
                            time_lost = corner_performances[corner['id']].get('metrics', {}).get('time_lost', 0.0)
                            
                            ax.annotate(
                                f"V{corner['id']}\n{score:.0f}/100\n+{time_lost:.2f}s",
                                xy=(apex_lon, apex_lat),
                                xytext=(5, 5),
                                textcoords='offset points',
                                fontsize=8,
                                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.9, edgecolor='black', linewidth=1)
                            )
            except Exception:
                continue
        
        # Légende
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=COLOR_GREEN, label='Excellent (>85/100)'),
            Patch(facecolor=COLOR_ORANGE, label='Moyen (70-85/100)'),
            Patch(facecolor=COLOR_RED, label='À travailler (<70/100)')
        ]
        ax.legend(handles=legend_elements, loc='best', frameon=False, fontsize=10)
        
        ax.set_aspect('equal')
        ax.grid(True, color=GRID_COLOR, alpha=0.5, linestyle='--')
        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        ax.set_title('Carte Performance - Heatmap des Virages', fontsize=16, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight')
        plt.close(fig)
        
        return True
    
    except Exception as e:
        warnings.warn(f"⚠️ Erreur plot_corner_heatmap : {str(e)}")
        return False


def generate_all_plots(df: pd.DataFrame, output_dir: str = "./plots") -> Dict[str, str]:
    """
    Génère les 8 graphiques style F1 AWS pour analyse karting professionnelle.
    
    Args:
        df: DataFrame avec colonnes nécessaires (doit avoir été traité par le pipeline)
        output_dir: Dossier de sortie pour les PNG
    
    Returns:
        Dictionnaire avec chemins des PNG générés (clés: noms des plots)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    plots = {
        'trajectory_2d': str(output_path / 'trajectory.png'),
        'speed_heatmap': str(output_path / 'speed_heatmap.png'),
        'lateral_g_chart': str(output_path / 'lateral_g.png'),
        'speed_trace': str(output_path / 'speed_trace.png'),
        'throttle_brake': str(output_path / 'throttle_brake.png'),
        'sector_times': str(output_path / 'sector_times.png'),
        'apex_precision': str(output_path / 'apex_precision.png'),
        'performance_radar': str(output_path / 'performance_radar.png'),
        'performance_score_breakdown': str(output_path / 'performance_score_breakdown.png'),
        'corner_heatmap': str(output_path / 'corner_heatmap.png')
    }
    
    # Mapping fonctions de plot
    plot_functions = {
        'trajectory_2d': plot_trajectory_2d,
        'speed_heatmap': plot_speed_heatmap,
        'lateral_g_chart': plot_lateral_g_chart,
        'speed_trace': plot_speed_trace,
        'throttle_brake': plot_throttle_brake,
        'sector_times': plot_sector_times,
        'apex_precision': plot_apex_precision,
        'performance_radar': plot_performance_radar,
        'performance_score_breakdown': plot_performance_score_breakdown,
        'corner_heatmap': plot_corner_heatmap
    }
    
    results = {}
    
    for plot_name, save_path in plots.items():
        try:
            plot_func = plot_functions[plot_name]
            success = plot_func(df, save_path)
            if success:
                results[plot_name] = save_path
            else:
                warnings.warn(f"⚠️ Échec génération {plot_name}")
        except Exception as e:
            warnings.warn(f"⚠️ Exception {plot_name} : {str(e)}")
    
    return results


def generate_all_plots_base64(df: pd.DataFrame) -> Dict[str, Optional[str]]:
    """
    Génère tous les graphiques et les retourne
    en base64 data URIs au lieu de fichiers disque.
    Survit aux redéploiements Docker.
    """
    import base64

    plots = {}
    plot_functions = {
        'trajectory_2d': plot_trajectory_2d,
        'speed_heatmap': plot_speed_heatmap,
        'lateral_g_chart': plot_lateral_g_chart,
        'speed_trace': plot_speed_trace,
        'throttle_brake': plot_throttle_brake,
        'sector_times': plot_sector_times,
        'apex_precision': plot_apex_precision,
        'performance_radar': plot_performance_radar,
        'performance_score_breakdown': plot_performance_score_breakdown,
        'corner_heatmap': plot_corner_heatmap,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        for name, func in plot_functions.items():
            try:
                save_path = os.path.join(tmpdir, f"{name}.png")
                success = func(df, save_path)
                if success and os.path.exists(save_path):
                    with open(save_path, 'rb') as f:
                        b64 = base64.b64encode(f.read()).decode('utf-8')
                    plots[name] = f"data:image/png;base64,{b64}"
                else:
                    plots[name] = None
            except Exception:
                plots[name] = None

    return plots
