import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
from src.analysis.geometry import calculate_trajectory_geometry, detect_corners, calculate_optimal_trajectory
from src.visualization.visualization import generate_all_plots

# Votre fichier test
file_path = r"C:\Users\Administrateur\Desktop\adria_final.csv"

print("=" * 70)
print("🏎️  APEX AI - PIPELINE COMPLET")
print("=" * 70)

# ÉTAPE 1 : Chargement
print("\n📁 [1/5] Chargement fichier...")
result = robust_load_telemetry(file_path)
if not result['success']:
    print(f"❌ Échec : {result['error']}")
    exit(1)
df = result['data']
print(f"✅ {result['metadata']['rows']} lignes | {result['metadata']['duration_seconds']:.1f}s")

# ÉTAPE 2 : Filtrage
print("\n🔧 [2/5] Filtrage Savitzky-Golay...")
df = apply_savgol_filter(df)
metrics = df.attrs.get('filtering', {})
print(f"✅ SNR {metrics.get('snr_db', 0):.1f} dB | Qualité: {metrics.get('quality', 'N/A')}")

# ÉTAPE 3 : Géométrie
print("\n📐 [3/5] Calcul géométrie trajectoire...")
df = calculate_trajectory_geometry(df)
print(f"✅ Heading, courbure, G latéral calculés")

# ÉTAPE 4 : Détection virages
print("\n🎯 [4/5] Détection apex et virages...")
df = detect_corners(df, min_lateral_g=0.08)  # Seuil adapté pour karting
corners = df.attrs.get('corners', {})
print(f"✅ {corners.get('total_corners', 0)} virages détectés")
print(f"   Max G latéral : {corners.get('max_lateral_g', 0):.2f}g")

# ÉTAPE 5 : Trajectoire optimale
print("\n⚡ [5/5] Calcul trajectoire optimale...")
df = calculate_optimal_trajectory(df)
print(f"✅ Vitesses optimales calculées")

# AFFICHAGE DÉTAILS VIRAGES
print("\n" + "=" * 70)
print("📊 ANALYSE DÉTAILLÉE PAR VIRAGE")
print("=" * 70)

corner_details = corners.get('corner_details', [])
for corner in corner_details[:5]:  # Afficher 5 premiers virages
    print(f"\n🏁 Virage {corner['id']} ({corner['type']})")
    print(f"   Vitesse apex : {corner['apex_speed_kmh']:.1f} km/h")
    if 'optimal_apex_speed_kmh' in corner:
        optimal_speed = corner['optimal_apex_speed_kmh']
        apex_speed = corner['apex_speed_kmh']
        speed_delta = apex_speed - optimal_speed
        efficiency = corner.get('speed_efficiency_pct', 0.0)
        print(f"   Vitesse optimale : {optimal_speed:.1f} km/h")
        print(f"   Écart : {speed_delta:+.1f} km/h")
        print(f"   Efficacité : {efficiency:.1f}%")
    print(f"   G latéral max : {corner['max_lateral_g']:.2f}g")
    print(f"   Distance : {corner.get('distance_m', 0):.1f}m | Durée : {corner.get('duration_s', 0):.2f}s")

# GÉNÉRATION GRAPHIQUES
print("\n" + "=" * 70)
print("🎨 GÉNÉRATION DES GRAPHIQUES")
print("=" * 70)

plots = generate_all_plots(df, output_dir="./plots")

print("\n✅ Graphiques générés :")
for name, path in plots.items():
    print(f"   📈 {name:20s} → {path}")

print("\n" + "=" * 70)
print("🎉 PIPELINE COMPLET TERMINÉ !")
print("=" * 70)
print(f"\n📂 Ouvrez le dossier './plots' pour voir les 8 graphiques")
