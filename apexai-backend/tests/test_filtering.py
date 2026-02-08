import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.data_loader import robust_load_telemetry
from src.core.signal_processing import apply_savgol_filter
import matplotlib.pyplot as plt

# Votre fichier de test
file_path = r"C:\Users\Administrateur\Desktop\adria_final.csv"

print("=" * 70)
print("🔬 TEST FILTRAGE SAVITZKY-GOLAY")
print("=" * 70)

# 1. Charger les données
print("\n📁 Chargement...")
result = robust_load_telemetry(file_path)

if not result['success']:
    print(f"❌ Échec : {result['error']}")
    exit(1)

df = result['data']
print(f"✅ {result['metadata']['rows']} lignes chargées")

# 2. Appliquer le filtre
print("\n🔧 Application du filtre Savitzky-Golay...")
df_filtered = apply_savgol_filter(df)

# 3. Afficher les métriques
if 'filtering' in df_filtered.attrs:
    metrics = df_filtered.attrs['filtering']
    print(f"\n📊 MÉTRIQUES DE FILTRAGE :")
    print(f"   Window length : {metrics.get('window_length', 'N/A')}")
    print(f"   Polynomial order : {metrics.get('polyorder', 'N/A')}")
    print(f"   SNR : {metrics.get('snr_db', 0):.2f} dB")
    print(f"   Qualité : {metrics.get('quality', 'N/A')}")
    print(f"   Déplacement moyen : {metrics.get('avg_displacement_m', 0):.2f}m")

# 4. Visualisation
print("\n📈 Génération du graphique...")

fig, axes = plt.subplots(2, 2, figsize=(15, 12))

# Graphique 1 : Trajectoire complète
ax1 = axes[0, 0]
ax1.plot(df_filtered['longitude_raw'], df_filtered['latitude_raw'], 
         'gray', alpha=0.4, linewidth=1, label='Brut')
ax1.plot(df_filtered['longitude_smooth'], df_filtered['latitude_smooth'], 
         'red', linewidth=2, label='Lissé')
ax1.scatter(df_filtered['longitude_smooth'].iloc[0], 
           df_filtered['latitude_smooth'].iloc[0], 
           c='green', s=100, zorder=5, label='Départ')
ax1.set_xlabel('Longitude')
ax1.set_ylabel('Latitude')
ax1.set_title('Trajectoire GPS - Circuit Complet')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Graphique 2 : Zoom sur un virage
ax2 = axes[0, 1]
# Prendre 200 points au milieu
start_idx = len(df_filtered) // 3
end_idx = start_idx + 200
zoom_df = df_filtered.iloc[start_idx:end_idx]

ax2.plot(zoom_df['longitude_raw'], zoom_df['latitude_raw'], 
         'o-', color='gray', alpha=0.5, markersize=3, label='Brut')
ax2.plot(zoom_df['longitude_smooth'], zoom_df['latitude_smooth'], 
         'o-', color='red', markersize=4, label='Lissé')
ax2.set_xlabel('Longitude')
ax2.set_ylabel('Latitude')
ax2.set_title('Zoom sur un Virage (effet du lissage)')
ax2.legend()
ax2.grid(True, alpha=0.3)

# Graphique 3 : Impact du filtrage (latitude)
ax3 = axes[1, 0]
sample_range = range(min(500, len(df_filtered)))
ax3.plot(sample_range, df_filtered['latitude_raw'].iloc[:len(sample_range)], 
         'gray', alpha=0.5, label='Brut')
ax3.plot(sample_range, df_filtered['latitude_smooth'].iloc[:len(sample_range)], 
         'red', linewidth=2, label='Lissé')
ax3.set_xlabel('Index')
ax3.set_ylabel('Latitude')
ax3.set_title('Effet du Lissage sur Latitude (500 premiers points)')
ax3.legend()
ax3.grid(True, alpha=0.3)

# Graphique 4 : Déplacement causé par le filtrage
ax4 = axes[1, 1]
displacement = ((df_filtered['latitude_smooth'] - df_filtered['latitude_raw'])**2 + 
                (df_filtered['longitude_smooth'] - df_filtered['longitude_raw'])**2)**0.5 * 111000  # Approx en mètres
ax4.plot(displacement.iloc[:len(sample_range)], 'blue', linewidth=1)
ax4.axhline(y=5, color='red', linestyle='--', label='Seuil 5m')
ax4.set_xlabel('Index')
ax4.set_ylabel('Déplacement (m)')
ax4.set_title('Déplacement causé par le Filtrage')
ax4.legend()
ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('filtering_analysis.png', dpi=150, bbox_inches='tight')
print(f"✅ Graphique sauvegardé : filtering_analysis.png")
print(f"\n📊 Ouvrez 'filtering_analysis.png' pour voir le résultat !")

print("\n" + "=" * 70)
print("✅ Test terminé")
print("=" * 70)
