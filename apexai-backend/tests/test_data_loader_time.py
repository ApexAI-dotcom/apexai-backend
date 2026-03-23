import pandas as pd
from src.core.data_loader import _validate_data

def test_validate_data_duplicated_time():
    # DataFrame avec toutes les colonnes requises
    df = pd.DataFrame({
        'latitude': [45.0] * 15,
        'longitude': [5.0] * 15,
        'speed': [60.0] * 15,
        'time': range(15),      # first time column
    })
    
    # Ajout d'une 2e colonne 'time' pour simuler le bug
    df.insert(4, 'time', range(15, 30), allow_duplicates=True)
    
    is_valid, df_clean, warnings = _validate_data(df)
    
    # Vérifier qu'il ne plante pas
    assert is_valid is True
    assert 'time' in df_clean.columns
    
    # La colonne time n'est plus dupliquée et on a bien utilisé la première
    assert isinstance(df_clean['time'], pd.Series)
    assert df_clean['time'].iloc[0] == 0
    
    # Vérifie le warning explicite
    assert any("Colonnes time dupliquées détectées" in w for w in warnings)

if __name__ == '__main__':
    test_validate_data_duplicated_time()
    print("✓ Test validé avec succès pour les colonnes time dupliquées.")
