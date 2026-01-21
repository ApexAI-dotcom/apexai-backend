#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Apex AI - Telegram Bot
Bot Telegram production-ready pour analyse de télémétrie karting
"""

import logging
import sys
from pathlib import Path
from dotenv import load_dotenv
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# Imports locaux (même package)
from .bot_config import LOG_FILE, TEMP_DIR
from .bot_handlers import (
    start_command, help_command, about_command, stats_command,
    handle_csv_document, button_callback
)
from .bot_database import init_database

# === CONFIGURATION LOGGING ===

def setup_logging() -> None:
    """Configure le système de logging."""
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Réduire verbosité de certaines bibliothèques
    logging.getLogger('httpx').setLevel(logging.WARNING)


# === HANDLER D'ERREURS GLOBAL ===

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handler global pour les erreurs non capturées.
    
    Args:
        update: Update Telegram
        context: Contexte de l'application
    """
    logger = logging.getLogger(__name__)
    
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
    
    # Envoyer message d'erreur à l'utilisateur si possible
    if update and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Une erreur s'est produite. L'équipe a été notifiée.\n"
                "Réessaie dans quelques instants ou contacte le support."
            )
        except Exception:
            pass


# === FONCTION PRINCIPALE ===

def main() -> None:
    """Point d'entrée principal du bot."""
    # Ajouter project_root au path pour imports src/
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    
    # Charger variables d'environnement (chercher .env à la racine)
    env_file = project_root / '.env'
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
    else:
        # Fallback: chercher dans config/
        env_file = project_root / 'config' / '.env'
        if env_file.exists():
            load_dotenv(dotenv_path=env_file)
        else:
            load_dotenv()  # Essayer chemin par défaut
    
    # Configuration logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Vérifier token
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        logger.error(f"Cherché dans: {env_file}")
        sys.exit(1)
    
    # Initialiser base de données
    init_database()
    
    logger.info("Starting Apex AI Telegram Bot...")
    
    # Créer application avec timeouts augmentés
    # Timeout pour téléchargement de fichiers (20MB max) : 2 minutes
    # Timeout pour requêtes API : 60 secondes
    # Timeout pour connexion : 30 secondes
    application = (
        Application.builder()
        .token(token)
        .connect_timeout(30.0)  # 30s pour établir connexion
        .read_timeout(60.0)  # 60s pour lire réponse API
        .write_timeout(60.0)  # 60s pour écrire requête
        .pool_timeout(30.0)  # 30s pour obtenir connexion du pool
        .get_updates_connect_timeout(30.0)  # 30s pour getUpdates
        .get_updates_read_timeout(30.0)  # 30s pour getUpdates read
        .get_updates_write_timeout(30.0)  # 30s pour getUpdates write
        .build()
    )
    
    # Enregistrer handlers de commandes
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Handler pour fichiers CSV
    application.add_handler(
        MessageHandler(
            filters.Document.FileExtension("csv"),
            handle_csv_document
        )
    )
    
    # Handler pour boutons inline
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Handler d'erreurs global
    application.add_error_handler(error_handler)
    
    # Démarrer le bot
    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
