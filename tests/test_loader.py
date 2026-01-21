import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.data_loader import robust_load_telemetry

# ========================================
# CONFIGUREZ VOS FICHIERS ICI
# ========================================

# Option 1 : Fichiers dans le même dossier qu'ApexAI
# test_files = [
#     "multi_corners.csv",
#     "mychron_test.csv",
#     "telemetrie_test.csv",
# ]

# Option 2 : Chemins complets Windows
test_files = [
    r"C:\Users\Administrateur\Desktop\telemetrie_monaco_light.csv",
    r"C:\Users\Administrateur\Desktop\adria_final.csv",
]


print("=" * 70)
print("🔬 APEX AI - TEST DATA LOADER")
print("=" * 70)

for file_path in test_files:
    print(f"\n📁 Fichier : {Path(file_path).name}")
    print("-" * 70)
    
    try:
        result = robust_load_telemetry(file_path)
        
        if result['success']:
            print("✅ SUCCÈS")
            print(f"   📊 Format détecté : {result['format']}")
            print(f"   📏 Lignes : {result['metadata']['rows']}")
            print(f"   📋 Colonnes : {result['metadata']['columns']}")
            print(f"   ⏱️  Durée : {result['metadata']['duration_seconds']:.2f}s")
            print(f"   🛣️  Circuit : {result['metadata']['circuit_length_m']:.0f}m")
            
            if result['warnings']:
                print(f"\n   ⚠️  Warnings :")
                for w in result['warnings']:
                    print(f"      • {w}")
            
            print(f"\n   📊 Aperçu des données :")
            print(result['data'][['latitude', 'longitude', 'speed', 'time']].head(3).to_string())
            
        else:
            print("❌ ÉCHEC")
            print(f"   Erreur : {result['error']}")
            if result['warnings']:
                print(f"   Warnings : {result['warnings']}")
    
    except FileNotFoundError:
        print(f"❌ FICHIER NON TROUVÉ : {file_path}")
        print(f"   Vérifiez le chemin ou mettez le fichier dans le dossier ApexAI")
    
    except Exception as e:
        print(f"❌ ERREUR INATTENDUE : {type(e).__name__}")
        print(f"   Message : {str(e)}")

print("\n" + "=" * 70)
print("✅ Tests terminés")
print("=" * 70)
