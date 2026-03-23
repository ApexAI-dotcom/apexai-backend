import pandas as pd
import numpy as np
import hashlib
import os
import json
import pytest
from src.core.data_loader import robust_load_telemetry, _validate_data, _normalize_columns
from src.api.services import _run_analysis_pipeline_sync
from datetime import datetime

def test_csv_semicolon_support(tmp_path):
    # Create a CSV with semicolon
    csv_content = "latitude;longitude;speed;time\n45.0;5.0;60.0;0.1\n45.1;5.1;61.0;0.2\n" * 30
    file_path = tmp_path / "test_semi.csv"
    file_path.write_text(csv_content)
    
    result = robust_load_telemetry(str(file_path))
    assert result["success"] is True
    assert "latitude" in result["data"].columns
    assert len(result["data"]) >= 50

def test_time_ms_conversion():
    df = pd.DataFrame({
        'latitude': [45.0]*10,
        'longitude': [5.0]*10,
        'speed': [60.0]*10,
        'time_ms': [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    })
    df_norm, warnings = _normalize_columns(df)
    assert df_norm['time'].iloc[0] == 0.1
    assert any("ms à s" in w for w in warnings)

def test_quality_gate_too_few_points(tmp_path):
    # Less than 50 points
    df = pd.DataFrame({
        'latitude': [45.0]*10,
        'longitude': [5.0]*10,
        'speed': [60.0]*10,
        'time': range(10)
    })
    csv_path = tmp_path / "low_points.csv"
    df.to_csv(csv_path, index=False)
    
    with pytest.raises(ValueError, match="pas assez de données exploitables"):
        _run_analysis_pipeline_sync(str(csv_path), [], "test_id", datetime.now())

def test_cache_key_determinism():
    content1 = b"lat,lon,speed,time\n45,5,60,0\n45,5,60,1"
    content2 = b"lat,lon,speed,time\n45,5,60,0\n45,5,60,2"
    
    def get_key(content, laps):
        file_hash = hashlib.sha256(content).hexdigest()
        norm_laps = str(sorted(laps)) if laps else "All"
        cache_str = f"{file_hash}_{norm_laps}_dry_none" # Simplified key logic from routes.py
        return hashlib.md5(cache_str.encode()).hexdigest()

    key1 = get_key(content1, [1, 2])
    key1_bis = get_key(content1, [2, 1])
    key2 = get_key(content2, [1, 2])
    
    assert key1 == key1_bis
    assert key1 != key2

def test_quality_gate_incoherent_laps(tmp_path):
    # Simulation d'une session longue avec un virage pour passer le gate des corners
    # mais un seul tour détecté (lap_number=1 partout)
    n = 200
    df = pd.DataFrame({
        'latitude': [45.0 + np.sin(i/20.0)*0.005 for i in range(n)],
        'longitude': [5.0 + i*0.0001 for i in range(n)],
        'speed': [80.0]*n,
        'time': [i*4.0 for i in range(n)], # 800s total
        'lap_number': [1]*n
    })
    csv_path = tmp_path / "incoherent_laps.csv"
    df.to_csv(csv_path, index=False)
    
    with pytest.raises(ValueError) as excinfo:
        _run_analysis_pipeline_sync(str(csv_path), [], "test_id", datetime.now())
    
    assert "Analyse rejetée" in str(excinfo.value)
    assert "détection des tours incohérente" in str(excinfo.value) or "temps calculé" in str(excinfo.value)

def test_non_regression_reference_file():
    # Path corrigé après recherche
    ref_path = r"C:\Users\Administrateur\Documents\Apex\csv1\4adria_ftest.csv"
    if not os.path.exists(ref_path):
        pytest.skip(f"Fichier de référence introuvable à {ref_path}")
    
    # Ne doit pas lever de ValueError (best_lap < 300s, plusieurs tours)
    result = _run_analysis_pipeline_sync(ref_path, [], "ref_test", datetime.now())
    assert result["success"] is True

if __name__ == "__main__":
    # Simple manual run if needed
    pass
