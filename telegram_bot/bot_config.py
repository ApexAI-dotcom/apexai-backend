#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Bot Configuration
Configuration et messages du bot Telegram
"""

from typing import Dict

# === CONSTANTES ===
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_ANALYSES_PER_HOUR = 3
ANALYSIS_TIMEOUT_SECONDS = 300  # 5 minutes
RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 heure

# Dossiers (chemins relatifs depuis project_root)
import os
from pathlib import Path

# Déterminer le répertoire racine du projet
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

TEMP_DIR = str(PROJECT_ROOT / "temp")
DB_PATH = str(PROJECT_ROOT / "data" / "bot_stats.db")
LOG_FILE = str(PROJECT_ROOT / "logs" / "bot.log")

# === MESSAGES ===

WELCOME_MESSAGE = """🏎️ **Bienvenue sur Apex AI - Race Engineer IA !**

Je suis ton ingénieur de course virtuel. Je peux analyser tes fichiers de télémétrie karting et te donner des insights de niveau professionnel.

📤 **Comment utiliser :**
1. Envoie-moi ton fichier CSV de télémétrie (MyChron, AiM, RaceBox, smartphone...)
2. J'analyse ta trajectoire, détecte tes virages et apex
3. Je génère 8 graphiques détaillés + un rapport de performance

⚡ **Format accepté :** `.csv`
📊 **Analyse inclut :**
• Détection automatique des virages et apex
• Analyse de trajectoire GPS
• Calcul des vitesses optimales
• Score de performance global
• 8 graphiques professionnels

Prêt à commencer ? Envoie ton fichier CSV ! 🚀"""


HELP_MESSAGE = """📚 **Guide d'utilisation Apex AI**

🔹 **Commandes disponibles :**
/start - Message de bienvenue
/help - Affiche ce guide
/stats - Tes statistiques personnelles
/about - Informations sur Apex AI

🔹 **Comment analyser un fichier :**
1. Envoie directement un fichier `.csv` au bot
2. Le bot détecte automatiquement le format
3. L'analyse prend environ 2 minutes
4. Tu reçois 8 graphiques + un rapport détaillé

🔹 **Formats CSV supportés :**
• MyChron (AIM)
• RaceBox
• Smartphone GPS (format standard)
• Télémétrie générique avec colonnes GPS

🔹 **Colonnes requises :**
• Latitude / Longitude (GPS)
• Speed / Vitesse
• Time / Temps (optionnel mais recommandé)

🔹 **Limites :**
• Taille max : 20 MB
• 3 analyses par heure
• Format : CSV uniquement

❓ **Problème ?** Contacte le support : @votrenom"""


ABOUT_MESSAGE = """🏁 **Apex AI - Race Engineer IA**

**Version :** 1.0.0
**Développé par :** Apex AI Team

**Technologies :**
• Analyse GPS de haute précision
• Détection automatique des apex
• Calcul de trajectoires optimales
• Visualisations professionnelles style F1 AWS

**Web App :** [À venir]
**Documentation :** [À venir]

**Contributeurs :** Merci à la communauté karting ! 🏎️"""


# Messages d'état
ANALYSIS_START = "⏳ **Analyse en cours...**\n\nVeuillez patienter environ 2 minutes.\n\n_Étape 1/4 : Chargement du fichier..._"
ANALYSIS_STEP_2 = "✅ Fichier chargé !\n_Étape 2/4 : Filtrage GPS..._"
ANALYSIS_STEP_3 = "✅ GPS filtré !\n_Étape 3/4 : Calcul géométrie..._"
ANALYSIS_STEP_4 = "✅ Géométrie calculée !\n_Étape 4/4 : Génération graphiques..._"

# Messages d'erreur
ERROR_FILE_TOO_LARGE = f"❌ **Fichier trop volumineux**\n\nTaille maximum : {MAX_FILE_SIZE_MB} MB\nTaille reçue : {{size}} MB"
ERROR_INVALID_FORMAT = "❌ **Format non reconnu**\n\nAssure-toi que le fichier est un CSV valide avec des colonnes GPS (Latitude, Longitude, Speed)."
ERROR_PIPELINE_FAILED = "❌ **Erreur lors de l'analyse**\n\nLe fichier n'a pas pu être traité. Vérifie qu'il contient bien des données GPS valides."
ERROR_RATE_LIMIT = f"⏰ **Limite atteinte**\n\nTu as déjà effectué {MAX_ANALYSES_PER_HOUR} analyses dans la dernière heure.\nRéessaie plus tard !"
ERROR_TIMEOUT = "⏱️ **Analyse trop longue**\n\nL'analyse a pris plus de 5 minutes et a été annulée.\nVérifie que le fichier n'est pas corrompu."
ERROR_NO_CSV = "❌ **Format non supporté**\n\nJe n'accepte que les fichiers `.csv` de télémétrie."

# Messages de succès
ANALYSIS_COMPLETE = "✅ **Analyse terminée avec succès !**\n\nVoici tes graphiques et résultats :"
SUCCESS_CLEANUP = "🧹 Fichiers temporaires nettoyés."

# Templates de rapport
def generate_report(corners_count: int, max_lateral_g: float, avg_speed: float, 
                   total_distance: float, duration: float) -> str:
    """Génère un message de rapport récapitulatif."""
    return f"""📊 **RAPPORT D'ANALYSE**

🏁 **Virages détectés :** {corners_count}
⚡ **G latéral max :** {max_lateral_g:.2f}g
📈 **Vitesse moyenne :** {avg_speed:.1f} km/h
📏 **Distance totale :** {total_distance:.0f} m
⏱️ **Durée :** {duration:.1f} s

📤 Besoin d'une autre analyse ? Envoie un nouveau CSV !"""


# Boutons inline
INLINE_KEYBOARD_START = [
    [{"text": "📤 Envoyer un CSV", "callback_data": "upload_csv"}]
]
