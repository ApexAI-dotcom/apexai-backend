#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de nettoyage et réorganisation du projet ApexAI
Usage: python cleanup_project.py [--dry-run] [--force]
"""

import os
import shutil
import sys
from pathlib import Path
from typing import List, Set
import argparse


class ProjectCleaner:
    """Nettoyeur de projet ApexAI"""
    
    def __init__(self, dry_run: bool = False, force: bool = False):
        self.project_root = Path.cwd()
        self.dry_run = dry_run
        self.force = force
        self.deleted_items: List[str] = []
        self.kept_items: List[str] = []
        self.moved_items: List[str] = []
        self.errors: List[str] = []
        
        # Mapping pour organiser les fichiers (source -> destination)
        self.files_to_organize = {
            # Bot Telegram -> telegram_bot/
            'telegram_bot.py': 'telegram_bot/telegram_bot.py',
            'bot_handlers.py': 'telegram_bot/bot_handlers.py',
            'bot_config.py': 'telegram_bot/bot_config.py',
            'bot_database.py': 'telegram_bot/bot_database.py',
            # Scripts de test -> tests/
            'test_scoring.py': 'tests/test_scoring.py',
            'test_*.py': 'tests/',  # Pattern
            'inspect_files.py': 'scripts/inspect_files.py',
            'debug.py': 'scripts/debug.py',
            # Requirements -> requirements/
            'requirements.txt': 'requirements/requirements.txt',
            'requirements_bot.txt': 'requirements/requirements_bot.txt',
            'requirements_api.txt': 'requirements/requirements_api.txt',
            # Config -> config/
            'env.example': 'config/env.example',
            '.env.example': 'config/.env.example',
            # CSV de test -> tests/data/
            '*.csv': 'tests/data/',  # Pattern (sauf à la racine si examples)
            # Logs -> logs/ (mais seront supprimés normalement)
            '*.log': 'logs/',  # Pattern
            'bot.log': 'logs/bot.log',
            # Database -> data/ (mais seront supprimés normalement)
            '*.db': 'data/',  # Pattern
            'bot_stats.db': 'data/bot_stats.db',
        }
        
        # Fichiers à SUPPRIMER (pas organisés)
        self.files_to_delete = {
            'bot.log',
            'bot_stats.db',
            'test_*.csv',
            '.gitignore_bot',  # Fusionner dans .gitignore
        }
        
        # Dossiers à SUPPRIMER
        self.folders_to_delete = {
            '__pycache__',
            '_pycache_',
            '.pytest_cache',
            'config',
            'plots',
            'fichier csv fictif',
            'fichier test',
            '.vscode',
            '.idea',
            'output',
            'temp',  # Sera recréé si nécessaire
        }
        
        # Patterns de dossiers à supprimer
        self.folder_patterns_to_delete = [
            'output_*',
            'temp_*',
            'plots_*',
            '*.egg-info',
        ]
        
        # Fichiers à SUPPRIMER (patterns)
        self.file_patterns_to_delete = [
            '*.pyc',
            '*.pyo',
            '*.log',
            '*.db',
            '*.png',
            '*.jpg',
            '*.jpeg',
            '.DS_Store',
            'Thumbs.db',
            '*.bak',
            '*.tmp',
        ]
        
        # Dossiers à GARDER (structure propre)
        self.folders_to_keep = {
            'src',
            'tests',
            'docs',
            'scripts',
            'telegram_bot',
            'requirements',
            'config',
            '.github',
        }
        
        # Fichiers importants à GARDER à la racine uniquement
        self.files_to_keep_at_root = {
            '.env',  # Ne pas déplacer, mais ne pas commiter
            '.gitignore',
            'README.md',
            'cleanup_project.py',
            'run_bot.py',  # Script de lancement bot
            'run_api.py',  # Script de lancement API
            'setup.py',  # Si existe
            'pyproject.toml',  # Si existe
            'Dockerfile',
            'render.yaml',
        }
    
    def clean(self):
        """Lancer le nettoyage complet"""
        print("=" * 70)
        print("🧹 APEX AI - NETTOYAGE DU PROJET")
        print("=" * 70)
        
        if self.dry_run:
            print("\n⚠️  MODE DRY-RUN : Aucune suppression ne sera effectuée\n")
        
        print(f"📂 Répertoire racine : {self.project_root}\n")
        
        # 1. Créer structure manquante (doit être fait avant organisation)
        self._create_missing_structure()
        
        # 2. Organiser les fichiers (déplacer dans bons dossiers)
        self._organize_files()
        
        # 3. Organiser les dossiers (fusionner contenu si nécessaire)
        self._organize_folders()
        
        # 4. Supprimer les dossiers inutiles
        self._clean_folders()
        
        # 5. Supprimer les fichiers inutiles
        self._clean_files()
        
        # 6. Nettoyer __pycache__ dans src/
        self._clean_pycache_recursive()
        
        # 7. Créer .gitignore
        self._create_gitignore()
        
        # 8. Créer README.md principal
        self._create_readme()
        
        # 9. Rapport final
        self._print_report()
    
    def _clean_folders(self):
        """Supprimer les dossiers inutiles"""
        print("📁 Nettoyage des dossiers...")
        
        for item in self.project_root.iterdir():
            if not item.is_dir():
                continue
            
            # Ignorer .git
            if item.name == '.git':
                continue
            
            should_delete = False
            reason = ""
            
            # Vérifier si dans la liste à supprimer
            if item.name in self.folders_to_delete:
                should_delete = True
                reason = "Liste noire"
            
            # Vérifier patterns
            elif any(self._match_pattern(item.name, pattern) for pattern in self.folder_patterns_to_delete):
                should_delete = True
                reason = "Pattern correspondant"
            
            # Garder les dossiers importants
            elif item.name in self.folders_to_keep:
                self.kept_items.append(f"📁 {item.name}/")
                continue
            
            if should_delete:
                try:
                    if not self.dry_run:
                        shutil.rmtree(item)
                    self.deleted_items.append(f"📁 {item.name}/ ({reason})")
                    print(f"  {'[DRY-RUN] ' if self.dry_run else ''}❌ Supprimé: {item.name}/")
                except Exception as e:
                    error_msg = f"Erreur suppression {item.name}/: {str(e)}"
                    self.errors.append(error_msg)
                    print(f"  ⚠️  {error_msg}")
    
    def _clean_files(self):
        """Supprimer les fichiers inutiles"""
        print("\n📄 Nettoyage des fichiers...")
        
        for item in self.project_root.iterdir():
            if not item.is_file():
                continue
            
            should_delete = False
            reason = ""
            
            # Vérifier extensions
            for pattern in self.file_patterns_to_delete:
                if self._match_pattern(item.name, pattern):
                    should_delete = True
                    reason = f"Extension: {pattern}"
                    break
            
            # Vérifier fichiers spécifiques
            if not should_delete:
                for pattern in self.files_to_delete:
                    if self._match_pattern(item.name, pattern):
                        should_delete = True
                        reason = f"Fichier: {pattern}"
                        break
            
            # Garder les fichiers importants
            if item.name in self.files_to_keep:
                self.kept_items.append(f"📄 {item.name}")
                continue
            
            if should_delete:
                try:
                    if not self.dry_run:
                        item.unlink()
                    self.deleted_items.append(f"📄 {item.name} ({reason})")
                    print(f"  {'[DRY-RUN] ' if self.dry_run else ''}❌ Supprimé: {item.name}")
                except Exception as e:
                    error_msg = f"Erreur suppression {item.name}: {str(e)}"
                    self.errors.append(error_msg)
                    print(f"  ⚠️  {error_msg}")
    
    def _clean_pycache_recursive(self):
        """Nettoyer tous les __pycache__ dans src/"""
        print("\n🗑️  Nettoyage des __pycache__ récursifs...")
        
        pycache_dirs = list(self.project_root.rglob('__pycache__'))
        pycache_dirs += list(self.project_root.rglob('*.pyc'))
        pycache_dirs += list(self.project_root.rglob('*.pyo'))
        
        for item in pycache_dirs:
            try:
                if item.is_dir():
                    if not self.dry_run:
                        shutil.rmtree(item)
                    self.deleted_items.append(f"📁 {item.relative_to(self.project_root)}/")
                    print(f"  {'[DRY-RUN] ' if self.dry_run else ''}❌ Supprimé: {item.relative_to(self.project_root)}/")
                else:
                    if not self.dry_run:
                        item.unlink()
                    self.deleted_items.append(f"📄 {item.relative_to(self.project_root)}")
                    print(f"  {'[DRY-RUN] ' if self.dry_run else ''}❌ Supprimé: {item.relative_to(self.project_root)}")
            except Exception as e:
                error_msg = f"Erreur suppression {item}: {str(e)}"
                self.errors.append(error_msg)
                print(f"  ⚠️  {error_msg}")
    
    def _match_pattern(self, name: str, pattern: str) -> bool:
        """Vérifie si un nom correspond à un pattern (support * et ?)"""
        import fnmatch
        return fnmatch.fnmatch(name, pattern)
    
    def _organize_files(self):
        """Organiser les fichiers dans les bons dossiers"""
        print("\n📦 Organisation des fichiers...")
        
        for item in self.project_root.iterdir():
            if not item.is_file():
                continue
            
            # Ignorer les fichiers déjà dans les bons dossiers
            try:
                relative_path = item.relative_to(self.project_root)
                if any(str(relative_path).startswith(d + '/') for d in 
                       ['src', 'tests', 'docs', 'scripts', 'telegram_bot', 'requirements', 'config']):
                    continue
            except ValueError:
                # Fichier pas dans le projet root (ne devrait pas arriver)
                continue
            
            # Ignorer les fichiers à garder à la racine
            if item.name in self.files_to_keep_at_root:
                self.kept_items.append(f"📄 {item.name} (conservé à la racine)")
                continue
            
            # Ignorer les fichiers cachés système
            if item.name.startswith('.') and item.name not in ['.gitignore', '.env']:
                continue
            
            moved = False
            
            # Vérifier mapping spécifique (priorité aux fichiers exacts)
            if item.name in self.files_to_organize:
                dest = self.files_to_organize[item.name]
                if self._move_file(item, dest):
                    moved = True
            
            # Vérifier patterns (seulement si pas déjà déplacé)
            if not moved:
                for pattern, dest_dir in self.files_to_organize.items():
                    if '*' in pattern and self._match_pattern(item.name, pattern):
                        # Si dest_dir est un dossier, ajouter le nom du fichier
                        if Path(dest_dir).is_dir() or not Path(dest_dir).suffix:
                            dest_path = Path(dest_dir) / item.name
                        else:
                            dest_path = Path(dest_dir)
                        if self._move_file(item, dest_path):
                            moved = True
                            break
            
            # Fichiers de test Python -> tests/ (si pas déjà organisé)
            if not moved and item.suffix == '.py' and (
                item.name.startswith('test_') or 
                item.name.startswith('Test_')
            ):
                dest_path = self.project_root / 'tests' / item.name
                if self._move_file(item, dest_path):
                    moved = True
            
            # Scripts utilitaires -> scripts/ (si pas déjà organisé)
            if not moved and item.suffix == '.py' and (
                'inspect' in item.name.lower() or
                'debug' in item.name.lower() or
                'util' in item.name.lower() or
                'helper' in item.name.lower()
            ):
                dest_path = self.project_root / 'scripts' / item.name
                if self._move_file(item, dest_path):
                    moved = True
            
            # Bot Python files -> telegram_bot/ (fallback)
            if not moved and item.suffix == '.py' and 'bot' in item.name.lower():
                dest_path = self.project_root / 'telegram_bot' / item.name
                if self._move_file(item, dest_path):
                    moved = True
            
            # Requirements -> requirements/ (fallback)
            if not moved and 'requirements' in item.name.lower():
                dest_path = self.project_root / 'requirements' / item.name
                if self._move_file(item, dest_path):
                    moved = True
    
    def _move_file(self, source: Path, dest: Path) -> bool:
        """Déplace un fichier vers une destination"""
        try:
            # Créer chemin absolu si relatif
            if not dest.is_absolute():
                dest = self.project_root / dest
            
            # Créer dossier parent si nécessaire
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Vérifier si destination existe
            if dest.exists():
                if self.force:
                    # Backup avec timestamp
                    backup_name = f"{dest.stem}.bak{dest.suffix}"
                    backup_path = dest.parent / backup_name
                    if not self.dry_run:
                        shutil.move(str(dest), str(backup_path))
                    print(f"  ⚠️  Backup: {dest.name} → {backup_name}")
                else:
                    print(f"  ⚠️  Existe déjà: {dest.relative_to(self.project_root)} (utilisez --force)")
                    return False
            
            # Déplacer le fichier
            if not self.dry_run:
                shutil.move(str(source), str(dest))
            
            self.moved_items.append(
                f"📄 {source.name} → {dest.relative_to(self.project_root)}"
            )
            print(f"  {'[DRY-RUN] ' if self.dry_run else ''}✅ Déplacé: {source.name} → {dest.relative_to(self.project_root)}")
            return True
        
        except Exception as e:
            error_msg = f"Erreur déplacement {source.name}: {str(e)}"
            self.errors.append(error_msg)
            print(f"  ⚠️  {error_msg}")
            return False
    
    def _organize_folders(self):
        """Organiser les dossiers (fusionner contenu)"""
        print("\n📁 Organisation des dossiers...")
        
        # Mapping dossiers source -> destination
        folders_to_move_content = {
            'fichier csv fictif': 'tests/data',
            'fichier test': 'tests/data',
            'config': 'docs/config',  # Déplacer config dans docs si existe
        }
        
        for source_name, dest_dir in folders_to_move_content.items():
            source_path = self.project_root / source_name
            if not source_path.exists() or not source_path.is_dir():
                continue
            
            dest_path = self.project_root / dest_dir
            dest_path.mkdir(parents=True, exist_ok=True)
            
            # Déplacer contenu du dossier source vers destination
            moved_count = 0
            for item in source_path.iterdir():
                try:
                    dest_item = dest_path / item.name
                    
                    # Gérer conflits
                    if dest_item.exists():
                        if self.force:
                            # Backup
                            backup_name = f"{item.stem}.bak{item.suffix if item.is_file() else ''}"
                            backup_path = dest_path / backup_name
                            if not self.dry_run:
                                if item.is_file():
                                    shutil.move(str(dest_item), str(backup_path))
                                else:
                                    shutil.move(str(dest_item), str(backup_path))
                        else:
                            print(f"  ⚠️  Conflit: {item.name} existe déjà dans {dest_dir}")
                            continue
                    
                    # Déplacer
                    if not self.dry_run:
                        shutil.move(str(item), str(dest_item))
                    
                    moved_count += 1
                    self.moved_items.append(
                        f"📄 {source_name}/{item.name} → {dest_dir}/{item.name}"
                    )
                
                except Exception as e:
                    error_msg = f"Erreur déplacement {item.name}: {str(e)}"
                    self.errors.append(error_msg)
                    print(f"  ⚠️  {error_msg}")
            
            # Supprimer dossier source s'il est vide
            try:
                if moved_count > 0:
                    if not self.dry_run:
                        # Vérifier si vide
                        remaining = list(source_path.iterdir())
                        if len(remaining) == 0:
                            source_path.rmdir()
                            print(f"  {'[DRY-RUN] ' if self.dry_run else ''}✅ Dossier vide supprimé: {source_name}/")
                        else:
                            print(f"  ⚠️  Dossier non vide, conservé: {source_name}/ ({len(remaining)} éléments restants)")
            except Exception as e:
                print(f"  ⚠️  Erreur suppression dossier {source_name}: {str(e)}")
    
    def _create_gitignore(self):
        """Créer un .gitignore complet"""
        print("\n📝 Création du .gitignore...")
        
        # Fusionner avec .gitignore_bot si existe
        gitignore_bot_path = self.project_root / '.gitignore_bot'
        gitignore_bot_content = ""
        if gitignore_bot_path.exists():
            try:
                gitignore_bot_content = gitignore_bot_path.read_text(encoding='utf-8')
                if not self.dry_run:
                    gitignore_bot_path.unlink()
                self.deleted_items.append(f"📄 .gitignore_bot (fusionné dans .gitignore)")
                print(f"  {'[DRY-RUN] ' if self.dry_run else ''}✅ Fusionné .gitignore_bot")
            except Exception as e:
                print(f"  ⚠️  Erreur lecture .gitignore_bot: {str(e)}")
        
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
build/
dist/
*.egg-info/
.eggs/

# Environment variables
.env
.env.local
.env.*.local
env.local

# Logs & Database
*.log
*.db
*.sqlite
*.sqlite3
bot.log
bot_stats.db

# Temporary files
temp/
tmp/
*.tmp
*.bak
*~
*.swp
*.swo

# Output & Media
output_*/
plots/
*.png
*.jpg
*.jpeg
*.gif
*.mp4
*.pdf

# CSV files (sauf examples)
*.csv
!example*.csv
!test_data/*.csv

# IDE
.vscode/
.idea/
*.iml
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.hypothesis/

# Jupyter
.ipynb_checkpoints/
*.ipynb

# Documentation build
docs/_build/
docs/_static/

# Project specific
logs/
data/
temp/
fichier csv fictif/
fichier test/
test_*.csv
inspect_files.py
debug.py

# Bot specific (mais organisés maintenant)
# telegram_bot/ est versionné, mais logs/ et data/ sont ignorés

# OS
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
"""
        
        # Fusionner avec .gitignore_bot si existe
        gitignore_bot_path = self.project_root / '.gitignore_bot'
        if gitignore_bot_path.exists():
            try:
                gitignore_bot_content = gitignore_bot_path.read_text(encoding='utf-8')
                # Ajouter contenu de .gitignore_bot
                gitignore_content = gitignore_content + "\n# Contenu de .gitignore_bot\n" + gitignore_bot_content + "\n"
                if not self.dry_run:
                    gitignore_bot_path.unlink()
                self.deleted_items.append(f"📄 .gitignore_bot (fusionné dans .gitignore)")
                print(f"  {'[DRY-RUN] ' if self.dry_run else ''}✅ Fusionné .gitignore_bot")
            except Exception as e:
                print(f"  ⚠️  Erreur lecture .gitignore_bot: {str(e)}")
        
        gitignore_path = self.project_root / '.gitignore'
        
        # Lire .gitignore existant pour le fusionner
        if gitignore_path.exists() and not self.force:
            try:
                existing_content = gitignore_path.read_text(encoding='utf-8')
                # Fusionner intelligemment
                existing_lines = set(existing_content.splitlines())
                new_lines = set(gitignore_content.splitlines())
                # Garder les lignes uniques de l'ancien
                unique_existing = existing_lines - new_lines
                if unique_existing:
                    gitignore_content = gitignore_content + "\n# Anciennes règles conservées\n" + "\n".join(sorted(unique_existing)) + "\n"
            except Exception:
                pass
        
        if not self.dry_run:
            gitignore_path.write_text(gitignore_content, encoding='utf-8')
        print(f"  {'[DRY-RUN] ' if self.dry_run else ''}✅ .gitignore créé/modifié")
    
    def _create_readme(self):
        """Créer README.md principal"""
        print("\n📖 Création du README.md...")
        
        readme_content = """# 🏎️ Apex AI - AI Race Engineer

Système d'analyse de télémétrie karting avec IA, scoring /100 et coaching personnalisé.

## 📦 Composants

- **Bot Telegram** : Interface conversationnelle pour upload et analyse
- **API REST** : Backend FastAPI pour intégration web (à venir)
- **Pipeline d'analyse** : Détection virages, scoring, coaching
- **Visualisations** : 10 graphiques professionnels style F1 AWS

## 🚀 Quick Start

### Bot Telegram

```bash
# Installer les dépendances
pip install -r requirements.txt -r requirements_bot.txt

# Configurer le token
cp env.example .env
# Éditer .env et ajouter TELEGRAM_BOT_TOKEN

# Lancer le bot
python telegram_bot.py
```

Consultez [README_BOT.md](README_BOT.md) pour plus de détails.

### Pipeline d'analyse

```python
from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
from src.analysis.geometry import calculate_trajectory_geometry, detect_corners
from src.analysis.scoring import calculate_performance_score
from src.visualization.visualization import generate_all_plots

# Charger données
result = robust_load_telemetry("file.csv")
df = result['data']

# Pipeline complet
df = apply_savgol_filter(df)
df = calculate_trajectory_geometry(df)
df = detect_corners(df)

# Scoring
score = calculate_performance_score(df, df.attrs['corners']['corner_details'])

# Visualisations
plots = generate_all_plots(df, output_dir="./plots")
```

## 📁 Structure du Projet

```
ApexAI/
├── src/
│   ├── core/           # Chargement et traitement données
│   ├── analysis/       # Scoring et coaching
│   ├── visualization/  # Génération graphiques
│   └── api/            # API REST (à venir)
├── tests/              # Tests unitaires
├── docs/               # Documentation
├── telegram_bot.py     # Bot Telegram
├── requirements.txt    # Dépendances principales
└── requirements_bot.txt # Dépendances bot
```

## 🎯 Fonctionnalités

### Analyse GPS
- Détection automatique de format CSV (MyChron, AiM, RaceBox, etc.)
- Lissage Savitzky-Golay pour trajectoires GPS
- Calcul géométrie (heading, courbure, G latéral)

### Détection de Virages
- Détection automatique des apex (22 virages typiques)
- Identification entry/apex/exit
- Calcul vitesses optimales théoriques

### Scoring /100
- **Précision Apex** (30 pts) : Distance apex réel vs idéal
- **Régularité** (20 pts) : Constance trajectoire
- **Vitesse Apex** (25 pts) : Efficacité vs optimal
- **Temps Secteur** (25 pts) : Performance S1/S2/S3

### Coaching IA
- 3-5 conseils hiérarchisés par impact (secondes)
- Catégories : freinage, apex, vitesse, trajectoire, global
- Explications détaillées avec repères visuels

### Visualisations
- Trajectoire GPS 2D avec apex
- Heatmap vitesse
- G latéral par virage
- Trace vitesse
- Throttle/Brake
- Temps secteurs
- Précision apex
- Radar performance
- Breakdown score
- Carte performance (heatmap virages)

## 🔧 Configuration

- **Python** : 3.10+
- **Dépendances** : Voir `requirements.txt`
- **Token Bot** : Obtenir depuis [@BotFather](https://t.me/BotFather)

## 📚 Documentation

- [README_BOT.md](README_BOT.md) : Guide bot Telegram
- [docs/](docs/) : Documentation détaillée

## 🤝 Contribution

Les contributions sont les bienvenues ! Ouvrir une issue ou une PR.

## 📄 Licence

[À définir]

---

**Apex AI Team** 🏎️
"""
        
        readme_path = self.project_root / 'README.md'
        if readme_path.exists() and not self.force:
            print(f"  ⚠️  README.md existe déjà. Utilisez --force pour le remplacer.")
        else:
            if not self.dry_run:
                readme_path.write_text(readme_content, encoding='utf-8')
            print(f"  {'[DRY-RUN] ' if self.dry_run else ''}✅ README.md créé/modifié")
    
    def _create_missing_structure(self):
        """Créer la structure de dossiers manquante"""
        print("\n📁 Création de la structure manquante...")
        
        folders_to_create = {
            'telegram_bot',  # Dossier pour bot Telegram
            'requirements',  # Dossier pour requirements
            'config',  # Dossier pour config
            'docs',
            'tests',
            'tests/data',  # Pour CSV de test
            'scripts',
            'logs',  # Pour logs (mais seront ignorés dans git)
            'data',  # Pour DB (mais seront ignorés dans git)
            'temp',  # Pour fichiers temporaires du bot
        }
        
        for folder_name in folders_to_create:
            folder_path = self.project_root / folder_name
            if not folder_path.exists():
                if not self.dry_run:
                    folder_path.mkdir(exist_ok=True)
                    # Créer .gitkeep pour s'assurer que le dossier est versionné
                    (folder_path / '.gitkeep').touch()
                print(f"  {'[DRY-RUN] ' if self.dry_run else ''}✅ Créé: {folder_name}/")
            else:
                print(f"  ℹ️  Existe déjà: {folder_name}/")
    
    def _print_report(self):
        """Afficher le rapport final"""
        print("\n" + "=" * 70)
        print("📊 RAPPORT DE NETTOYAGE")
        print("=" * 70)
        
        print(f"\n✅ Éléments conservés : {len(self.kept_items)}")
        if self.kept_items:
            for item in sorted(self.kept_items)[:10]:
                print(f"  {item}")
            if len(self.kept_items) > 10:
                print(f"  ... et {len(self.kept_items) - 10} autres")
        
        print(f"\n📦 Éléments déplacés : {len(self.moved_items)}")
        if self.moved_items:
            for item in sorted(self.moved_items)[:20]:
                print(f"  {item}")
            if len(self.moved_items) > 20:
                print(f"  ... et {len(self.moved_items) - 20} autres")
        
        print(f"\n❌ Éléments supprimés : {len(self.deleted_items)}")
        if self.deleted_items:
            for item in sorted(self.deleted_items)[:20]:
                print(f"  {item}")
            if len(self.deleted_items) > 20:
                print(f"  ... et {len(self.deleted_items) - 20} autres")
        
        if self.errors:
            print(f"\n⚠️  Erreurs rencontrées : {len(self.errors)}")
            for error in self.errors:
                print(f"  {error}")
        
        print("\n" + "=" * 70)
        if self.dry_run:
            print("✅ MODE DRY-RUN TERMINÉ")
            print("💡 Exécutez sans --dry-run pour effectuer le nettoyage réel")
        else:
            print("✅ NETTOYAGE TERMINÉ")
        print("=" * 70)


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description='Nettoyer et réorganiser le projet ApexAI'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mode simulation (aucune suppression)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Forcer la réécriture des fichiers existants'
    )
    
    args = parser.parse_args()
    
    # Confirmation si pas en dry-run
    if not args.dry_run:
        response = input("\n⚠️  Êtes-vous sûr de vouloir nettoyer le projet ? (oui/non): ")
        if response.lower() not in ['oui', 'o', 'yes', 'y']:
            print("❌ Nettoyage annulé.")
            return
    
    cleaner = ProjectCleaner(dry_run=args.dry_run, force=args.force)
    cleaner.clean()


if __name__ == '__main__':
    main()
