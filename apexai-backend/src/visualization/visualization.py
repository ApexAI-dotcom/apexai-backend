#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Visualization (Karting Pro)
Création de 8 graphiques style F1 AWS pour analyse professionnelle
"""

# Backend headless OBLIGATOIRE pour Railway/Render (pas de display)
import matplotlib
matplotlib.use("Agg")

import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
from typing import Dict, Optional
import warnings
import tempfile
import os

# Brand ApexAI Dark Theme
BG_DARK = '#0a0a0f'
BG_CARD = '#13131a'
BG_PANEL = '#1a1a2e'
COLOR_ORANGE = '#f97316'
COLOR_PURPLE = '#8b5cf6'
COLOR_GREEN = '#22c55e'
COLOR_RED = '#ef4444'
COLOR_YELLOW = '#eab308'
COLOR_TEXT = '#e2e8f0'
COLOR_MUTED = '#64748b'
GRID_COLOR = '#1e293b'
FIG_SIZE = (12, 7)
DPI = 120

# Style global matplotlib dark
plt.rcParams.update({
    'figure.facecolor': BG_DARK,
    'axes.facecolor': BG_CARD,
    'axes.edgecolor': BG_PANEL,
    'axes.labelcolor': COLOR_TEXT,
    'axes.titlecolor': COLOR_TEXT,
    'xtick.color': COLOR_MUTED,
    'ytick.color': COLOR_MUTED,
    'text.color': COLOR_TEXT,
    'grid.color': GRID_COLOR,
    'grid.alpha': 0.5,
    'legend.facecolor': BG_PANEL,
    'legend.edgecolor': BG_PANEL,
    'legend.labelcolor': COLOR_TEXT,
})


def _style_ax(ax, title: str, xlabel: str = '', ylabel: str = ''):
    """Applique le dark theme brand ApexAI sur un axe."""
    ax.set_facecolor(BG_CARD)
    ax.set_title(title, color=COLOR_TEXT, fontsize=15, fontweight='bold', pad=12)
    if xlabel:
        ax.set_xlabel(xlabel, color=COLOR_MUTED, fontsize=11)
    if ylabel:
        ax.set_ylabel(ylabel, color=COLOR_MUTED, fontsize=11)
    ax.tick_params(colors=COLOR_MUTED)
    ax.grid(True, color=GRID_COLOR, alpha=0.5, linestyle='--', linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_edgecolor(BG_PANEL)


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
    try:
        required_cols = ['longitude_smooth', 'latitude_smooth', 'speed']
        if not all(col in df.columns for col in required_cols):
            return False
        
        lon = pd.to_numeric(df['longitude_smooth'], errors='coerce').values
        lat = pd.to_numeric(df['latitude_smooth'], errors='coerce').values
        speed = pd.to_numeric(df['speed'], errors='coerce').values
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        fig.patch.set_facecolor(BG_DARK)
        ax.set_facecolor(BG_DARK)
        
        # Trajectoire colorée par vitesse
        points = np.array([lon, lat]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        from matplotlib.collections import LineCollection
        from matplotlib.colors import LinearSegmentedColormap
        
        # Colormap brand : violet → orange → vert
        cmap = LinearSegmentedColormap.from_list(
            'apex', [COLOR_PURPLE, COLOR_ORANGE, COLOR_GREEN]
        )
        lc = LineCollection(segments, cmap=cmap, linewidth=2.5, alpha=0.9)
        lc.set_array(speed)
        ax.add_collection(lc)
        ax.autoscale()
        
        # Apex markers : un seul marqueur + label par corner_id (pas un par passage)
        corner_analysis = df.attrs.get('corner_analysis', [])
        if corner_analysis:
            plotted_ids = set()
            for corner in corner_analysis:
                cid = corner.get('corner_id')
                apex_lat = corner.get('apex_lat')
                apex_lon = corner.get('apex_lon')
                if cid is None or apex_lat is None or apex_lon is None or cid in plotted_ids:
                    continue
                plotted_ids.add(cid)
                ax.scatter(apex_lon, apex_lat, marker='*', s=180,
                          color=COLOR_ORANGE, edgecolors=BG_DARK,
                          linewidths=0.8, zorder=10)
                ax.annotate(f'V{int(cid)}', xy=(apex_lon, apex_lat),
                           xytext=(4, 6), textcoords='offset points',
                           fontsize=8, color=COLOR_ORANGE, fontweight='bold')
        elif 'is_apex' in df.columns and 'corner_id' in df.columns:
            from collections import defaultdict
            apex_mask = df['is_apex'].fillna(False)
            if apex_mask.any():
                by_cid = defaultdict(list)
                for i in np.where(apex_mask.values)[0]:
                    cid = df.iloc[i]['corner_id']
                    if pd.notna(cid):
                        by_cid[int(cid)].append((lon[i], lat[i]))
                plotted_ids = set()
                for cid, points in by_cid.items():
                    if cid in plotted_ids or not points:
                        continue
                    plotted_ids.add(cid)
                    med_lon = np.median([p[0] for p in points])
                    med_lat = np.median([p[1] for p in points])
                    ax.scatter(med_lon, med_lat, marker='*', s=180,
                              color=COLOR_ORANGE, edgecolors=BG_DARK,
                              linewidths=0.8, zorder=10)
                    ax.annotate(f'V{cid}', xy=(med_lon, med_lat),
                               xytext=(4, 6), textcoords='offset points',
                               fontsize=8, color=COLOR_ORANGE, fontweight='bold')
        
        # Start / Finish
        ax.scatter(lon[0], lat[0], s=120, color=COLOR_GREEN, 
                  marker='o', edgecolors=BG_DARK, zorder=11, label='Départ')
        ax.scatter(lon[-1], lat[-1], s=120, color=COLOR_RED, 
                  marker='s', edgecolors=BG_DARK, zorder=11, label='Arrivée')
        
        cbar = plt.colorbar(lc, ax=ax)
        cbar.set_label('Vitesse (km/h)', color=COLOR_MUTED, fontsize=10)
        cbar.ax.yaxis.set_tick_params(color=COLOR_MUTED)
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color=COLOR_MUTED)
        cbar.outline.set_edgecolor(BG_PANEL)
        
        _style_ax(ax, '🏎  Trajectoire GPS — Circuit Complet', 'Longitude', 'Latitude')
        ax.set_aspect('equal')
        ax.legend(facecolor=BG_PANEL, edgecolor=BG_PANEL, labelcolor=COLOR_TEXT, fontsize=9)
        
        fig.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight', facecolor=BG_DARK)
        plt.close(fig)
        return True
    except Exception as e:
        warnings.warn(f"⚠️ plot_trajectory_2d : {e}")
        return False


def plot_speed_heatmap(df: pd.DataFrame, save_path: str) -> bool:
    try:
        required_cols = ['longitude_smooth', 'latitude_smooth', 'speed']
        if not all(col in df.columns for col in required_cols):
            return False
        
        lon = pd.to_numeric(df['longitude_smooth'], errors='coerce').values
        lat = pd.to_numeric(df['latitude_smooth'], errors='coerce').values
        speed = pd.to_numeric(df['speed'], errors='coerce').values
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        fig.patch.set_facecolor(BG_DARK)
        
        from matplotlib.colors import LinearSegmentedColormap
        cmap = LinearSegmentedColormap.from_list(
            'speed_heat', [COLOR_RED, COLOR_YELLOW, COLOR_GREEN]
        )
        
        scatter = ax.scatter(lon, lat, c=speed, cmap=cmap, s=8, alpha=0.85,
                           vmin=np.nanpercentile(speed, 5), 
                           vmax=np.nanpercentile(speed, 95))
        
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('Vitesse (km/h)', color=COLOR_MUTED, fontsize=10)
        cbar.ax.yaxis.set_tick_params(color=COLOR_MUTED)
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color=COLOR_MUTED)
        cbar.outline.set_edgecolor(BG_PANEL)
        
        _style_ax(ax, '🌡  Heatmap Vitesse — Zones Critiques', 'Longitude', 'Latitude')
        ax.set_aspect('equal')
        
        fig.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight', facecolor=BG_DARK)
        plt.close(fig)
        return True
    except Exception as e:
        warnings.warn(f"⚠️ plot_speed_heatmap : {e}")
        return False


def plot_lateral_g_chart(df: pd.DataFrame, save_path: str) -> bool:
    try:
        # Utiliser colonnes directes du df (plus df.attrs)
        if 'corner_id' not in df.columns or 'lateral_g' not in df.columns:
            # Fallback : essayer lateral_g depuis colonnes disponibles
            if 'lateral_g' not in df.columns:
                warnings.warn("⚠️ lateral_g manquant pour lateral_g_chart")
                return False
        
        # Agréger G max par virage
        g_col = 'lateral_g' if 'lateral_g' in df.columns else 'lateral_g_smooth'
        corner_col = 'corner_id' if 'corner_id' in df.columns else None
        
        if corner_col:
            corner_df = df[df['corner_id'] > 0].copy()
            corner_df['lateral_g_abs'] = pd.to_numeric(corner_df[g_col], errors='coerce').abs()
            grouped = corner_df.groupby('corner_id')['lateral_g_abs'].max().reset_index()
            corner_ids = grouped['corner_id'].tolist()
            max_g = grouped['lateral_g_abs'].tolist()
        else:
            return False
        
        colors = [COLOR_GREEN if g < 1.5 else COLOR_ORANGE if g < 2.0 else COLOR_RED 
                 for g in max_g]
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        fig.patch.set_facecolor(BG_DARK)
        
        bars = ax.bar(corner_ids, max_g, color=colors, alpha=0.85, 
                     edgecolor=BG_DARK, linewidth=0.5, width=0.7)
        
        ax.axhline(y=2.0, color=COLOR_ORANGE, linestyle='--', linewidth=1.5, 
                  alpha=0.7, label='Limite conseillée (2.0g)')
        ax.axhline(y=1.5, color=COLOR_GREEN, linestyle='--', linewidth=1.5, 
                  alpha=0.7, label='Target optimal (1.5g)')
        
        for cid, g in zip(corner_ids, max_g):
            ax.text(cid, g + 0.03, f'{g:.1f}g', ha='center', 
                   va='bottom', fontsize=8, color=COLOR_MUTED)
        
        _style_ax(ax, '⚡ G Latéral — Par Virage', 'Virage', 'G latéral (g)')
        ax.legend(fontsize=9)
        
        fig.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight', facecolor=BG_DARK)
        plt.close(fig)
        return True
    except Exception as e:
        warnings.warn(f"⚠️ plot_lateral_g_chart : {e}")
        return False


def plot_speed_trace(df: pd.DataFrame, save_path: str) -> bool:
    try:
        if 'cumulative_distance' not in df.columns or 'speed' not in df.columns:
            return False
        
        dist = pd.to_numeric(df['cumulative_distance'], errors='coerce').values
        speed = pd.to_numeric(df['speed'], errors='coerce').values
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        fig.patch.set_facecolor(BG_DARK)
        
        # Zones virages en fond
        if 'corner_id' in df.columns:
            corner_ids = df['corner_id'].values
            in_corner = False
            start_d = 0
            for i, cid in enumerate(corner_ids):
                if cid > 0 and not in_corner:
                    start_d = dist[i]
                    in_corner = True
                elif cid == 0 and in_corner:
                    ax.axvspan(start_d, dist[i], alpha=0.12, 
                              color=COLOR_PURPLE, zorder=0)
                    in_corner = False
        
        # Ligne vitesse avec gradient d'épaisseur
        ax.plot(dist, speed, color=COLOR_ORANGE, linewidth=2, 
               alpha=0.9, label='Vitesse', zorder=2)
        ax.fill_between(dist, 0, speed, color=COLOR_ORANGE, alpha=0.08, zorder=1)
        
        # Vitesse moyenne
        avg = np.nanmean(speed)
        ax.axhline(y=avg, color=COLOR_PURPLE, linestyle='--', 
                  linewidth=1.2, alpha=0.7, 
                  label=f'Moyenne {avg:.0f} km/h')
        
        # Apex markers
        if 'is_apex' in df.columns:
            apex_mask = df['is_apex'] == True
            if apex_mask.any():
                apex_d = dist[apex_mask.values]
                apex_s = speed[apex_mask.values]
                ax.scatter(apex_d, apex_s, marker='v', s=80, 
                          color=COLOR_ORANGE, edgecolors=BG_DARK,
                          linewidths=0.5, zorder=5, label='Apex')
        
        # Secteurs
        if len(dist) > 0 and not np.isnan(dist[-1]):
            total = dist[-1]
            for frac, label in [(1/3, 'S1'), (2/3, 'S2')]:
                ax.axvline(x=total*frac, color=COLOR_MUTED, 
                          linestyle=':', alpha=0.4, linewidth=1)
            for frac, label in [(1/6, 'S1'), (1/2, 'S2'), (5/6, 'S3')]:
                ypos = np.nanmax(speed) * 0.95
                ax.text(total*frac, ypos, label, ha='center', 
                       fontsize=10, color=COLOR_MUTED,
                       bbox=dict(boxstyle='round,pad=0.2', 
                                facecolor=BG_PANEL, alpha=0.8,
                                edgecolor='none'))
        
        _style_ax(ax, '📈 Trace de Vitesse — Tour Complet', 
                 'Distance (m)', 'Vitesse (km/h)')
        ax.legend(fontsize=9)
        
        fig.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight', facecolor=BG_DARK)
        plt.close(fig)
        return True
    except Exception as e:
        warnings.warn(f"⚠️ plot_speed_trace : {e}")
        return False


def plot_throttle_brake(df: pd.DataFrame, save_path: str) -> bool:
    try:
        if 'cumulative_distance' not in df.columns:
            return False
        if 'throttle' not in df.columns or 'brake' not in df.columns:
            # Simuler depuis vitesse si pas de throttle/brake
            if 'speed' not in df.columns:
                return False
            dist = pd.to_numeric(df['cumulative_distance'], errors='coerce').values
            speed = pd.to_numeric(df['speed'], errors='coerce').values
            speed_diff = np.gradient(speed)
            throttle = np.clip(speed_diff * 20, 0, 100)
            brake = np.clip(-speed_diff * 20, 0, 100)
        else:
            dist = pd.to_numeric(df['cumulative_distance'], errors='coerce').values
            throttle = pd.to_numeric(df['throttle'], errors='coerce').fillna(0).values
            brake = pd.to_numeric(df['brake'], errors='coerce').fillna(0).values
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=FIG_SIZE, dpi=DPI, 
                                        sharex=True, height_ratios=[1, 1])
        fig.patch.set_facecolor(BG_DARK)
        
        # Throttle
        ax1.fill_between(dist, 0, throttle, color=COLOR_GREEN, alpha=0.7)
        ax1.plot(dist, throttle, color=COLOR_GREEN, linewidth=1.2)
        _style_ax(ax1, '🟢 Accélérateur', ylabel='% Gaz')
        ax1.set_ylim(0, 110)
        
        # Brake
        ax2.fill_between(dist, 0, brake, color=COLOR_RED, alpha=0.7)
        ax2.plot(dist, brake, color=COLOR_RED, linewidth=1.2)
        _style_ax(ax2, '🔴 Freinage', 'Distance (m)', '% Frein')
        ax2.set_ylim(0, 110)
        
        # Apex markers sur les deux
        if 'is_apex' in df.columns:
            apex_mask = df['is_apex'] == True
            if apex_mask.any():
                apex_d = dist[apex_mask.values]
                for ad in apex_d:
                    ax1.axvline(x=ad, color=COLOR_ORANGE, 
                               linestyle=':', alpha=0.4, linewidth=1)
                    ax2.axvline(x=ad, color=COLOR_ORANGE, 
                               linestyle=':', alpha=0.4, linewidth=1)
        
        fig.suptitle('🎮 Throttle & Brake — Application', 
                    color=COLOR_TEXT, fontsize=15, fontweight='bold')
        fig.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight', facecolor=BG_DARK)
        plt.close(fig)
        return True
    except Exception as e:
        warnings.warn(f"⚠️ plot_throttle_brake : {e}")
        return False


def plot_sector_times(df: pd.DataFrame, save_path: str) -> bool:
    try:
        if 'cumulative_distance' not in df.columns or 'time' not in df.columns:
            return False
        
        dist = pd.to_numeric(df['cumulative_distance'], errors='coerce').values
        time = pd.to_numeric(df['time'], errors='coerce').values
        
        if len(dist) == 0 or np.isnan(dist[-1]):
            return False
        
        total_dist = dist[-1]
        s1_idx = np.argmin(np.abs(dist - total_dist/3))
        s2_idx = np.argmin(np.abs(dist - 2*total_dist/3))
        
        s1 = float(time[s1_idx] - time[0])
        s2 = float(time[s2_idx] - time[s1_idx])
        s3 = float(time[-1] - time[s2_idx])
        sector_times = [s1, s2, s3]
        optimal_times = [t * 0.95 for t in sector_times]
        
        fig, ax = plt.subplots(figsize=(10, 6), dpi=DPI)
        fig.patch.set_facecolor(BG_DARK)
        
        x = np.arange(3)
        w = 0.35
        bars1 = ax.bar(x - w/2, sector_times, w, 
                      label='Votre temps', color=COLOR_PURPLE, 
                      alpha=0.85, edgecolor=BG_DARK, linewidth=0.5)
        bars2 = ax.bar(x + w/2, optimal_times, w, 
                      label='Optimal (-5%)', color=COLOR_GREEN, 
                      alpha=0.6, edgecolor=BG_DARK, linewidth=0.5)
        
        total = time[-1] - time[0]
        for i, (t, opt) in enumerate(zip(sector_times, optimal_times)):
            delta = t - opt
            ax.text(i, max(t, opt) + total*0.01, 
                   f'+{delta:.2f}s', ha='center', 
                   va='bottom', fontsize=10, 
                   color=COLOR_ORANGE, fontweight='bold')
        
        _style_ax(ax, '⏱  Analyse Secteurs — Temps Comparés', 
                 'Secteur', 'Temps (s)')
        ax.set_xticks(x)
        ax.set_xticklabels(['S1', 'S2', 'S3'], color=COLOR_TEXT, fontsize=12)
        ax.legend(fontsize=9)
        
        fig.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight', facecolor=BG_DARK)
        plt.close(fig)
        return True
    except Exception as e:
        warnings.warn(f"⚠️ plot_sector_times : {e}")
        return False


def plot_apex_precision(df: pd.DataFrame, save_path: str) -> bool:
    try:
        # Utiliser corner_id et apex_distance_error depuis df si dispo
        if 'corner_id' not in df.columns:
            return False
        
        # Agréger par virage : apex_distance_error ou écart de vitesse
        corner_ids = []
        deviations = []
        
        if 'apex_distance_error' in df.columns:
            grp = df[df['corner_id'] > 0].groupby('corner_id')['apex_distance_error'].mean()
            corner_ids = grp.index.tolist()
            deviations = grp.values.tolist()
        elif 'is_apex' in df.columns and 'speed' in df.columns:
            # Fallback : écart vitesse apex par virage
            apex_df = df[df['is_apex'] == True]
            if 'apex_speed_optimal' in df.columns:
                for cid, grp in apex_df.groupby('corner_id'):
                    real = grp['speed'].mean()
                    opt = grp['apex_speed_optimal'].mean() if 'apex_speed_optimal' in grp else real
                    corner_ids.append(cid)
                    deviations.append(abs(opt - real) * 0.1)
            else:
                return False
        else:
            return False
        
        if not corner_ids:
            return False
        
        colors = [COLOR_GREEN if d < 1.0 else COLOR_ORANGE if d < 2.5 else COLOR_RED 
                 for d in deviations]
        
        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        fig.patch.set_facecolor(BG_DARK)
        
        y_pos = range(len(corner_ids))
        bars = ax.barh(list(y_pos), deviations, color=colors, 
                      alpha=0.85, edgecolor=BG_DARK, linewidth=0.5)
        
        ax.axvline(x=1.0, color=COLOR_GREEN, linestyle='--', 
                  linewidth=1.5, alpha=0.7, label='Excellent (<1m)')
        ax.axvline(x=2.5, color=COLOR_ORANGE, linestyle='--', 
                  linewidth=1.5, alpha=0.7, label='Acceptable (<2.5m)')
        
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels([f'V{cid}' for cid in corner_ids], 
                          color=COLOR_TEXT, fontsize=9)
        
        for pos, (cid, dev) in enumerate(zip(corner_ids, deviations)):
            ax.text(dev + 0.05, pos, f'{dev:.1f}m', 
                   va='center', fontsize=8, color=COLOR_MUTED)
        
        _style_ax(ax, '🎯 Précision Apex — Écart par Virage', 
                 'Écart (m)', '')
        ax.legend(fontsize=9)
        
        fig.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight', facecolor=BG_DARK)
        plt.close(fig)
        return True
    except Exception as e:
        warnings.warn(f"⚠️ plot_apex_precision : {e}")
        return False


def plot_performance_radar(df: pd.DataFrame, save_path: str) -> bool:
    try:
        # Scores depuis attrs si dispo, sinon calculer
        if 'score_data' in df.attrs:
            score_data = df.attrs['score_data']
            breakdown = score_data.get('breakdown', {})
            apex = min(100, breakdown.get('apex_precision', 10) / 30 * 100)
            consistency = min(100, breakdown.get('trajectory_consistency', 10) / 20 * 100)
            speed = min(100, breakdown.get('apex_speed', 10) / 25 * 100)
            sectors = min(100, breakdown.get('sector_times', 10) / 25 * 100)
        else:
            apex = 55.0
            consistency = 70.0
            speed = 60.0
            sectors = 65.0
        
        # Score global depuis attribut si dispo
        overall = df.attrs.get('overall_score', (apex + consistency + speed + sectors) / 4)
        
        categories = ['Précision\nApex', 'Régularité', 'Vitesse\nApex', 'Secteurs']
        values = [apex, consistency, speed, sectors]
        
        angles = np.linspace(0, 2*np.pi, len(categories), endpoint=False).tolist()
        values_plot = values + values[:1]
        angles_plot = angles + angles[:1]
        
        fig, ax = plt.subplots(figsize=(9, 9), dpi=DPI, 
                              subplot_kw=dict(projection='polar'))
        fig.patch.set_facecolor(BG_DARK)
        ax.set_facecolor(BG_DARK)
        
        # Grille
        ax.set_ylim(0, 100)
        ax.set_yticks([25, 50, 75, 100])
        ax.set_yticklabels(['25', '50', '75', '100'], 
                          color=COLOR_MUTED, fontsize=8)
        ax.grid(True, color=GRID_COLOR, alpha=0.6, linestyle='--')
        ax.spines['polar'].set_color(BG_PANEL)
        
        # Fill gradient
        ax.fill(angles_plot, values_plot, color=COLOR_PURPLE, alpha=0.2)
        ax.plot(angles_plot, values_plot, color=COLOR_ORANGE, 
               linewidth=2.5, marker='o', markersize=6,
               markerfacecolor=COLOR_ORANGE, markeredgecolor=BG_DARK)
        
        ax.set_xticks(angles)
        ax.set_xticklabels(categories, color=COLOR_TEXT, fontsize=11)
        
        # Score au centre
        ax.text(0, -35, f'{overall:.0f}', ha='center', va='center',
               fontsize=32, fontweight='bold', color=COLOR_ORANGE,
               transform=ax.transData)
        ax.text(0, -55, '/100', ha='center', va='center',
               fontsize=14, color=COLOR_MUTED,
               transform=ax.transData)
        
        ax.set_title('🏆 Performance Radar', color=COLOR_TEXT, 
                    fontsize=15, fontweight='bold', pad=20)
        
        fig.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight', facecolor=BG_DARK)
        plt.close(fig)
        return True
    except Exception as e:
        warnings.warn(f"⚠️ plot_performance_radar : {e}")
        return False


def plot_performance_score_breakdown(df: pd.DataFrame, save_path: str) -> bool:
    try:
        if 'score_data' in df.attrs:
            score_data = df.attrs['score_data']
            breakdown = score_data.get('breakdown', {})
            overall = score_data.get('overall_score', 55.0)
            grade = score_data.get('grade', 'C')
        else:
            breakdown = {
                'apex_precision': 10.0,
                'trajectory_consistency': 15.0,
                'apex_speed': 15.0,
                'sector_times': 15.0
            }
            overall = 55.0
            grade = 'D'
        
        categories = ['Précision Apex', 'Régularité', 'Vitesse Apex', 'Temps Secteurs']
        values = [
            breakdown.get('apex_precision', 10.0),
            breakdown.get('trajectory_consistency', 15.0),
            breakdown.get('apex_speed', 15.0),
            breakdown.get('sector_times', 15.0)
        ]
        max_scores = [30.0, 20.0, 25.0, 25.0]
        pcts = [v/m*100 for v, m in zip(values, max_scores)]
        
        colors = [COLOR_GREEN if p >= 70 else COLOR_ORANGE if p >= 50 else COLOR_RED 
                 for p in pcts]
        
        fig, ax = plt.subplots(figsize=(10, 6), dpi=DPI)
        fig.patch.set_facecolor(BG_DARK)
        
        y_pos = range(len(categories))
        
        # Barres background (max)
        ax.barh(list(y_pos), max_scores, color=BG_PANEL, 
               alpha=0.5, edgecolor='none', height=0.6)
        # Barres réelles
        bars = ax.barh(list(y_pos), values, color=colors, 
                      alpha=0.85, edgecolor='none', height=0.6)
        
        # Labels
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(categories, color=COLOR_TEXT, fontsize=11)
        
        for pos, (v, m, p) in enumerate(zip(values, max_scores, pcts)):
            ax.text(m + 0.3, pos, f'{v:.1f}/{m:.0f} ({p:.0f}%)', 
                   va='center', fontsize=9, color=COLOR_MUTED)
        
        # Score global en haut à droite
        color_grade = COLOR_GREEN if overall >= 80 else COLOR_ORANGE if overall >= 60 else COLOR_RED
        ax.text(0.98, 0.95, f'{overall:.0f}/100', transform=ax.transAxes,
               fontsize=28, fontweight='bold', color=color_grade,
               ha='right', va='top')
        ax.text(0.98, 0.82, f'Grade {grade}', transform=ax.transAxes,
               fontsize=14, color=COLOR_MUTED, ha='right', va='top')
        
        _style_ax(ax, '📊 Score de Performance — Breakdown', 
                 'Points', '')
        ax.set_xlim(0, max(max_scores) * 1.3)
        
        fig.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight', facecolor=BG_DARK)
        plt.close(fig)
        return True
    except Exception as e:
        warnings.warn(f"⚠️ plot_performance_score_breakdown : {e}")
        return False


def plot_corner_heatmap(df: pd.DataFrame, save_path: str) -> bool:
    try:
        lon_col = 'longitude_smooth' if 'longitude_smooth' in df.columns else 'longitude'
        lat_col = 'latitude_smooth' if 'latitude_smooth' in df.columns else 'latitude'
        if lon_col not in df.columns or lat_col not in df.columns:
            return False
        lon_all = pd.to_numeric(df[lon_col], errors='coerce').values
        lat_all = pd.to_numeric(df[lat_col], errors='coerce').values

        fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)
        fig.patch.set_facecolor(BG_DARK)
        ax.set_facecolor(BG_DARK)

        # 1. Trajectoire GPS complète en fond (fine, sombre)
        ax.plot(lon_all, lat_all, color=BG_PANEL, linewidth=1.2, alpha=0.7, zorder=1)

        # 2. Cercles aux positions GPS des virages (pas de lignes entre eux)
        corners = df.attrs.get('corner_analysis', [])
        corners_with_gps = [c for c in corners if c.get('apex_lat') is not None and c.get('apex_lon') is not None]

        def _haversine_m(lat1, lon1, lat2, lon2):
            R = 6371000
            dlat = math.radians(lat2 - lat1)
            dlon = math.radians(lon2 - lon1)
            a = (math.sin(dlat / 2) ** 2 +
                 math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
                 math.sin(dlon / 2) ** 2)
            return R * 2 * math.asin(math.sqrt(a))

        # Offsets des labels pour éviter chevauchements (chicanes V7/V8)
        label_offsets = {}
        for i, c1 in enumerate(corners_with_gps):
            offset = (6, 6)
            for j, c2 in enumerate(corners_with_gps):
                if i == j:
                    continue
                dist = _haversine_m(c1['apex_lat'], c1['apex_lon'], c2['apex_lat'], c2['apex_lon'])
                if dist < 40:
                    offset = (6, 12) if i < j else (6, -18)
                    break
            label_offsets[c1.get('corner_id')] = offset

        for corner in corners_with_gps:
            apex_lon = corner.get('apex_lon')
            apex_lat = corner.get('apex_lat')
            score = corner.get('score', 70)
            corner_id = corner.get('corner_id', '?')
            color = COLOR_GREEN if score >= 80 else COLOR_ORANGE if score >= 65 else COLOR_RED
            ax.scatter(apex_lon, apex_lat, s=400, color=color, zorder=5,
                      edgecolors=COLOR_TEXT, linewidths=1.5)
            xytext = label_offsets.get(corner_id, (6, 6))
            ax.annotate(f'V{corner_id}\n{score:.0f}',
                       xy=(apex_lon, apex_lat),
                       xytext=xytext, textcoords='offset points',
                       fontsize=8, color=COLOR_TEXT, fontweight='bold', zorder=6)

        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=COLOR_GREEN, label='Excellent ≥80'),
            Patch(facecolor=COLOR_ORANGE, label='Moyen 65-80'),
            Patch(facecolor=COLOR_RED, label='À travailler <65'),
        ]
        ax.legend(handles=legend_elements, facecolor=BG_PANEL,
                 edgecolor=BG_PANEL, labelcolor=COLOR_TEXT, fontsize=9)
        _style_ax(ax, '🗺  Carte Performance — Heatmap Virages', 'Longitude', 'Latitude')
        ax.set_aspect('equal')
        fig.tight_layout()
        plt.savefig(save_path, dpi=DPI, bbox_inches='tight', facecolor=BG_DARK)
        plt.close(fig)
        return True
    except Exception as e:
        warnings.warn(f"⚠️ plot_corner_heatmap : {e}")
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
