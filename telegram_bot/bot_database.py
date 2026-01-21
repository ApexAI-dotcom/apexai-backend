#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Bot Database
Gestion de la base de données SQLite pour les statistiques
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional
from pathlib import Path

from .bot_config import DB_PATH, MAX_ANALYSES_PER_HOUR, RATE_LIMIT_WINDOW_SECONDS

logger = logging.getLogger(__name__)


def init_database() -> None:
    """
    Initialise la base de données SQLite.
    Crée la table si elle n'existe pas.
    """
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_stats (
            user_id INTEGER PRIMARY KEY,
            total_analyses INTEGER DEFAULT 0,
            last_analysis_date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            analysis_date TEXT DEFAULT CURRENT_TIMESTAMP,
            file_name TEXT,
            corners_detected INTEGER,
            FOREIGN KEY (user_id) REFERENCES user_stats(user_id)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


def get_user_stats(user_id: int) -> Dict[str, any]:
    """
    Récupère les statistiques d'un utilisateur.
    
    Args:
        user_id: ID Telegram de l'utilisateur
    
    Returns:
        Dictionnaire avec total_analyses et last_analysis
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT total_analyses, last_analysis_date
        FROM user_stats
        WHERE user_id = ?
    """, (user_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return {
            'total_analyses': result[0],
            'last_analysis': result[1]
        }
    else:
        return {
            'total_analyses': 0,
            'last_analysis': None
        }


def increment_user_analyses(user_id: int) -> None:
    """
    Incrémente le compteur d'analyses d'un utilisateur.
    Crée l'utilisateur s'il n'existe pas.
    
    Args:
        user_id: ID Telegram de l'utilisateur
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    # Vérifier si l'utilisateur existe
    cursor.execute("SELECT total_analyses FROM user_stats WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    
    if exists:
        # Mettre à jour
        cursor.execute("""
            UPDATE user_stats
            SET total_analyses = total_analyses + 1,
                last_analysis_date = ?
            WHERE user_id = ?
        """, (now, user_id))
    else:
        # Créer
        cursor.execute("""
            INSERT INTO user_stats (user_id, total_analyses, last_analysis_date)
            VALUES (?, 1, ?)
        """, (user_id, now))
    
    conn.commit()
    conn.close()
    logger.info(f"Incremented analyses for user {user_id}")


def check_rate_limit(user_id: int) -> bool:
    """
    Vérifie si l'utilisateur respecte la limite de rate limiting.
    
    Args:
        user_id: ID Telegram de l'utilisateur
    
    Returns:
        True si OK, False si limite atteinte
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Vérifier analyses dans la dernière heure
    cutoff_time = (datetime.now() - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)).isoformat()
    
    cursor.execute("""
        SELECT COUNT(*) FROM analysis_log
        WHERE user_id = ? AND analysis_date > ?
    """, (user_id, cutoff_time))
    
    count = cursor.fetchone()[0]
    conn.close()
    
    return count < MAX_ANALYSES_PER_HOUR


def log_analysis(user_id: int, file_name: str, corners_detected: int) -> None:
    """
    Enregistre une analyse dans le log.
    
    Args:
        user_id: ID Telegram de l'utilisateur
        file_name: Nom du fichier analysé
        corners_detected: Nombre de virages détectés
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO analysis_log (user_id, file_name, corners_detected)
        VALUES (?, ?, ?)
    """, (user_id, file_name, corners_detected))
    
    conn.commit()
    conn.close()
    logger.info(f"Logged analysis for user {user_id}: {corners_detected} corners")
