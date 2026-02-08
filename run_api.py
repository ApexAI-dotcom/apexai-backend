#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de lancement de l'API REST Apex AI (depuis la racine du projet)
Délègue vers apexai-backend/run_api.py
Usage: python run_api.py
"""

import subprocess
import sys
from pathlib import Path

backend_dir = Path(__file__).parent / "apexai-backend"
run_script = backend_dir / "run_api.py"

if run_script.exists():
    sys.exit(subprocess.call([sys.executable, str(run_script)], cwd=str(backend_dir)))
else:
    print("Erreur: apexai-backend/run_api.py introuvable.")
    sys.exit(1)
