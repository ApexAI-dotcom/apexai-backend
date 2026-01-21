#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Bot Handlers
Logique métier du bot Telegram
"""

import asyncio
import logging
import uuid
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# Ajouter project_root au path pour imports src/
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Imports locaux (même package)
from .bot_config import (
    MAX_FILE_SIZE_BYTES, MAX_ANALYSES_PER_HOUR, ANALYSIS_TIMEOUT_SECONDS,
    TEMP_DIR, WELCOME_MESSAGE, HELP_MESSAGE, ABOUT_MESSAGE,
    ERROR_FILE_TOO_LARGE, ERROR_INVALID_FORMAT, ERROR_PIPELINE_FAILED,
    ERROR_RATE_LIMIT, ERROR_TIMEOUT, ERROR_NO_CSV, ANALYSIS_START,
    ANALYSIS_STEP_2, ANALYSIS_STEP_3, ANALYSIS_STEP_4,
    ANALYSIS_COMPLETE, generate_report, INLINE_KEYBOARD_START
)
from .bot_database import (
    get_user_stats, increment_user_analyses, check_rate_limit,
    init_database, log_analysis
)

# Imports pipeline
from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
from src.analysis.geometry import (
    calculate_trajectory_geometry, detect_corners, calculate_optimal_trajectory
)
from src.analysis.scoring import calculate_performance_score
from src.analysis.performance_metrics import analyze_corner_performance
from src.analysis.coaching import generate_coaching_advice
from src.visualization.visualization import generate_all_plots

logger = logging.getLogger(__name__)


# === HANDLERS DE COMMANDES ===

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler pour la commande /start.
    Affiche le message de bienvenue avec bouton inline.
    """
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")
    
    keyboard = InlineKeyboardMarkup(INLINE_KEYBOARD_START)
    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode='Markdown',
        reply_markup=keyboard
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler pour la commande /help."""
    await update.message.reply_text(HELP_MESSAGE, parse_mode='Markdown')


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler pour la commande /about."""
    await update.message.reply_text(ABOUT_MESSAGE, parse_mode='Markdown')


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler pour la commande /stats.
    Affiche les statistiques personnelles de l'utilisateur.
    """
    user_id = update.effective_user.id
    stats = get_user_stats(user_id)
    
    message = f"""📊 **Tes Statistiques**

🔢 **Analyses effectuées :** {stats['total_analyses']}
📅 **Dernière analyse :** {stats['last_analysis'] or 'Jamais'}

Continue à améliorer ta performance ! 🏎️"""
    
    await update.message.reply_text(message, parse_mode='Markdown')


# === HANDLER DE FICHIERS CSV ===

async def handle_csv_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler principal pour les fichiers CSV uploadés.
    Orchestre tout le pipeline d'analyse.
    """
    user = update.effective_user
    user_id = user.id
    
    # Vérifier rate limiting
    if not check_rate_limit(user_id):
        await update.message.reply_text(ERROR_RATE_LIMIT)
        return
    
    document = update.message.document
    
    # Vérifier format
    if not document.file_name.lower().endswith('.csv'):
        await update.message.reply_text(ERROR_NO_CSV)
        return
    
    # Vérifier taille
    if document.file_size > MAX_FILE_SIZE_BYTES:
        size_mb = document.file_size / (1024 * 1024)
        await update.message.reply_text(ERROR_FILE_TOO_LARGE.format(size=f"{size_mb:.1f}"))
        return
    
    # Message initial
    status_msg = await update.message.reply_text("📥 **Téléchargement du fichier...**\n\nVeuillez patienter...")
    
    # Typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # Créer dossier temp si inexistant
    temp_dir = Path(TEMP_DIR)
    temp_dir.mkdir(exist_ok=True)
    
    # Générer nom de fichier unique
    file_id = str(uuid.uuid4())
    temp_file_path = temp_dir / f"{user_id}_{file_id}.csv"
    
    try:
        # Télécharger le fichier avec timeout (2 minutes pour 20MB max)
        file = await asyncio.wait_for(
            context.bot.get_file(document.file_id),
            timeout=120.0  # 2 minutes pour obtenir le file object
        )
        await asyncio.wait_for(
            file.download_to_drive(temp_file_path),
            timeout=180.0  # 3 minutes pour télécharger (20MB @ ~1Mbps = ~2.5 min)
        )
        logger.info(f"File downloaded: {temp_file_path} ({document.file_size / 1024 / 1024:.2f} MB) for user {user_id}")
        
        # Mettre à jour le message : fichier téléchargé, analyse en cours
        await status_msg.edit_text(ANALYSIS_START)
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        # Exécuter le pipeline avec timeout
        await asyncio.wait_for(
            _run_analysis_pipeline(update, context, status_msg, temp_file_path, user_id),
            timeout=ANALYSIS_TIMEOUT_SECONDS
        )
        
        # Incrémenter compteur
        increment_user_analyses(user_id)
        
    except asyncio.TimeoutError as e:
        logger.error(f"Timeout for user {user_id}: {str(e)}")
        await status_msg.edit_text(
            "⏱️ **Timeout lors du téléchargement ou de l'analyse**\n\n"
            "Le fichier est peut-être trop volumineux ou la connexion est lente.\n"
            "Réessaie avec un fichier plus petit ou une meilleure connexion."
        )
        await _cleanup_temp_file(temp_file_path)
    
    except Exception as e:
        logger.error(f"Error processing CSV for user {user_id}: {str(e)}", exc_info=True)
        await status_msg.edit_text(ERROR_PIPELINE_FAILED)
        await _cleanup_temp_file(temp_file_path)


async def _run_analysis_pipeline(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status_msg,
    file_path: Path,
    user_id: int
) -> None:
    """
    Exécute le pipeline d'analyse complet.
    """
    chat_id = update.effective_chat.id
    
    try:
        # ÉTAPE 1 : Chargement
        await status_msg.edit_text(ANALYSIS_STEP_2)
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        
        result = robust_load_telemetry(str(file_path))
        if not result['success']:
            await status_msg.edit_text(ERROR_INVALID_FORMAT)
            return
        
        df = result['data']
        logger.info(f"Data loaded: {len(df)} rows for user {user_id}")
        
        # ÉTAPE 2 : Filtrage
        await status_msg.edit_text(ANALYSIS_STEP_3)
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        
        df = apply_savgol_filter(df)
        
        # ÉTAPE 3 : Géométrie
        await status_msg.edit_text(ANALYSIS_STEP_4)
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        
        df = calculate_trajectory_geometry(df)
        df = detect_corners(df, min_lateral_g=0.08)
        df = calculate_optimal_trajectory(df)
        
        # ÉTAPE 4 : Visualisation
        output_dir = Path(TEMP_DIR) / f"plots_{user_id}_{uuid.uuid4()}"
        plots = generate_all_plots(df, output_dir=str(output_dir))
        
        logger.info(f"Generated {len(plots)} plots for user {user_id}")
        
        # Envoyer les graphiques
        await status_msg.edit_text(ANALYSIS_COMPLETE)
        await _send_plots(context, chat_id, plots)
        
        # Calculer le score et coaching
        corners_meta = df.attrs.get('corners', {})
        corner_details = corners_meta.get('corner_details', [])
        
        try:
            score_data = calculate_performance_score(df, corner_details)
            corner_analysis = [analyze_corner_performance(df, c) for c in corner_details]
            coaching_advice = generate_coaching_advice(df, corner_details, score_data, corner_analysis)
            
            # Envoyer rapport récapitulatif avec score
            report = f"""🏁 **ANALYSE COMPLÈTE** 🏁

📊 **Score Global : {score_data['overall_score']}/100** (Grade {score_data['grade']})

**Breakdown :**
• Précision Apex : {score_data['breakdown']['apex_precision']:.1f}/30
• Régularité : {score_data['breakdown']['trajectory_consistency']:.1f}/20
• Vitesse Apex : {score_data['breakdown']['apex_speed']:.1f}/25
• Temps Secteur : {score_data['breakdown']['sector_times']:.1f}/25

🎯 **Top 3 Conseils Prioritaires :**

{chr(10).join([f"{i+1}. {advice['message']}" for i, advice in enumerate(coaching_advice[:3])]) if coaching_advice else 'Aucun conseil disponible'}

💡 **Détails :**
• Virages détectés : {len(corner_details)}
• Meilleurs virages : {', '.join(map(str, score_data['details']['best_corners'])) if score_data['details']['best_corners'] else 'N/A'}
• À travailler : {', '.join(map(str, score_data['details']['worst_corners'])) if score_data['details']['worst_corners'] else 'N/A'}
• Distance apex moyenne : {score_data['details']['avg_apex_distance']:.2f}m
• Efficacité vitesse : {score_data['details']['avg_apex_speed_efficiency']*100:.1f}%

📈 Consulte les graphiques pour l'analyse visuelle détaillée !"""
            
            await context.bot.send_message(chat_id=chat_id, text=report, parse_mode='Markdown')
        
        except Exception as e:
            logger.warning(f"Error calculating score/coaching for user {user_id}: {str(e)}", exc_info=True)
            # Envoyer rapport simplifié sans score
            report = f"""🏁 **ANALYSE COMPLÈTE** 🏁

📊 **RAPPORT D'ANALYSE**

🏁 **Virages détectés :** {len(corner_details)}
⚡ **G latéral max :** {corners_meta.get('max_lateral_g', 0.0):.2f}g
📈 **Vitesse moyenne :** {corners_meta.get('avg_speed_kmh', 0.0):.1f} km/h
📏 **Distance totale :** {corners_meta.get('total_distance_m', 0.0):.0f} m

⚠️ Le calcul du score détaillé n'a pas pu être effectué, mais l'analyse GPS est complète.

📈 Consulte les graphiques pour l'analyse visuelle détaillée !"""
            
            await context.bot.send_message(chat_id=chat_id, text=report, parse_mode='Markdown')
        
        # Logger l'analyse
        file_name = file_path.name
        log_analysis(user_id, file_name, len(corner_details))
        
        # Nettoyage
        await _cleanup_temp_files(file_path, output_dir)
        
    except Exception as e:
        logger.error(f"Pipeline error for user {user_id}: {str(e)}", exc_info=True)
        raise


async def _send_plots(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    plots: Dict[str, str]
) -> None:
    """
    Envoie les 8 graphiques avec captions descriptives.
    """
    plot_captions = {
        'trajectory_2d': '🏎️ **Trajectoire GPS complète**\nVue d\'ensemble du circuit avec apex marqués',
        'speed_heatmap': '⚡ **Heatmap de vitesse**\nZones rapides (vert) vs lentes (rouge)',
        'lateral_g_chart': '📊 **G latéral par virage**\nAccélération latérale avec limites de sécurité',
        'speed_trace': '📈 **Trace de vitesse**\nVitesse le long du tour avec zones de virages',
        'throttle_brake': '🎮 **Throttle & Brake**\nUtilisation des commandes pendant le tour',
        'sector_times': '⏱️ **Temps par secteur**\nComparaison S1, S2, S3',
        'apex_precision': '🎯 **Précision des apex**\nÉcart entre apex réel et optimal',
        'performance_radar': '🌟 **Score de performance**\nRadar chart global',
        'performance_score_breakdown': '📊 **Breakdown du score**\nDétail par catégorie de performance',
        'corner_heatmap': '🗺️ **Carte performance**\nVirages colorés selon performance'
    }
    
    plot_order = [
        'trajectory_2d', 'speed_heatmap', 'lateral_g_chart', 'speed_trace',
        'throttle_brake', 'sector_times', 'apex_precision', 'performance_radar',
        'performance_score_breakdown', 'corner_heatmap'
    ]
    
    for plot_name in plot_order:
        if plot_name in plots:
            plot_path = Path(plots[plot_name])
            if plot_path.exists():
                caption = plot_captions.get(plot_name, '📊 Graphique d\'analyse')
                with open(plot_path, 'rb') as photo:
                    await context.bot.send_photo(
                        chat_id=chat_id,
                        photo=photo,
                        caption=caption,
                        parse_mode='Markdown'
                    )
                await asyncio.sleep(0.5)  # Petit délai entre envois


async def _cleanup_temp_file(file_path: Path) -> None:
    """Supprime un fichier temporaire."""
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        logger.warning(f"Error cleaning up {file_path}: {str(e)}")


async def _cleanup_temp_files(file_path: Path, plots_dir: Path) -> None:
    """Nettoie tous les fichiers temporaires."""
    try:
        # Supprimer fichier CSV
        if file_path.exists():
            file_path.unlink()
        
        # Supprimer dossier plots
        if plots_dir.exists():
            import shutil
            shutil.rmtree(plots_dir)
        
        logger.info(f"Cleaned up temp files for {file_path}")
    except Exception as e:
        logger.warning(f"Error cleaning up temp files: {str(e)}")


# === CALLBACK HANDLERS ===

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler pour les boutons inline."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "upload_csv":
        await query.edit_message_text(
            "📤 **Envoie ton fichier CSV maintenant !**\n\nJe détecterai automatiquement le format et lancerai l'analyse."
        )
