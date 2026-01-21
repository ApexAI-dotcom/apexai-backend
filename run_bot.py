#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de lancement du bot Telegram Apex AI
Usage: python run_bot.py
"""

import sys
from pathlib import Path

# Ajouter le répertoire racine au path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Importer et lancer le bot
from telegram_bot.telegram_bot import main

if __name__ == '__main__':
    main()
