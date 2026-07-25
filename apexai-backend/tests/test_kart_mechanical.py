import pytest
import os
import tempfile
import pandas as pd
from unittest import mock
from src.core.kart_mechanical import compute_file_signature, extract_motec_metadata, parse_kart_mechanical

@pytest.fixture
def sample_csv_path():
    # Temporary AiM/MoTeC-style CSV. Header keys are quoted, exactly like the
    # real exports (cf. tests/fixtures/adria_4laps.csv.gz) — extract_motec_metadata
    # only picks up lines shaped `"Key","Value"`.
    csv_content = '''"Format","MoTeC CSV File","","","Workbook"
"Venue","Le Mans","","","Worksheet"
"Vehicle","","","","Vehicle Desc"
"Driver","Test Driver","","","Engine ID"
"Device","AiM Ported"
"Comment","","","","Session",""
"Log Date","14/07/2026","","","Origin Time","0","s"
"Log Time","14:30:00","","","Start Time","0","s"
"Sample Rate","50","Hz","","End Time","600","s"
"Duration","0:10:00.000","","","Start Distance"
"Range","entire outing","","","End Distance"
"Beacon Markers","52.500 103.000"


"Time","RPM","Water Temp","Speed","Accel_Lat","Accel_Lon","Battery"
"s","rpm","C","km/h","g","g","V"
0.0,12000,85.5,55.0,0.5,-1.2,12.5
1.0,12500,86.0,80.0,1.2,0.8,12.4
2.0,11000,86.5,45.0,-1.5,-2.1,12.4
3.0,10500,87.0,40.0,0.2,-0.5,12.3
'''
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(csv_content)
    yield path
    os.remove(path)

def test_extract_motec_metadata(sample_csv_path):
    metadata = extract_motec_metadata(sample_csv_path)
    assert metadata.get("Venue") == "Le Mans"
    assert metadata.get("Driver") == "Test Driver"
    assert metadata.get("Log Date") == "14/07/2026"
    assert metadata.get("Duration") == "0:10:00.000"

def test_compute_file_signature(sample_csv_path):
    metadata = extract_motec_metadata(sample_csv_path)
    sig1 = compute_file_signature(sample_csv_path, metadata)
    sig2 = compute_file_signature(sample_csv_path, metadata)
    assert sig1 == sig2
    assert len(sig1) == 64  # SHA256 hex length
    
def test_parse_kart_mechanical(sample_csv_path):
    # data_loader is exercised by its own tests; here we stub the CSV reading so
    # the assertions target the aggregation logic only. Standard MoTeC headers
    # are 14 lines, hence skiprows=14.
    with mock.patch('src.core.kart_mechanical._detect_format') as mock_detect:
        with mock.patch('src.core.kart_mechanical._parse_with_pandas') as mock_parse:
            with mock.patch('src.core.kart_mechanical._extract_beacon_markers') as mock_beacons:
                
                mock_detect.return_value = 14
                
                # Mock DataFrame matching our data
                df = pd.DataFrame({
                    "time": [0.0, 1.0, 2.0, 3.0],
                    "rpm": [12000, 12500, 11000, 10500],
                    "water temp": [85.5, 86.0, 86.5, 87.0],
                    "speed": [55.0, 80.0, 45.0, 40.0],
                    "accel_lat": [0.5, 1.2, -1.5, 0.2],
                    "accel_lon": [-1.2, 0.8, -2.1, -0.5],
                    "battery": [12.5, 12.4, 12.4, 12.3]
                })
                mock_parse.return_value = df
                # Realistic beacon spacing: the parser discards laps <= 10 s as
                # spurious markers, so 2 laps of ~50 s.
                mock_beacons.return_value = [0.0, 52.5, 103.0] # 2 laps
                
                res = parse_kart_mechanical(sample_csv_path)
                
                assert res["success"] is True
                assert res["signature"] is not None
                
                aggs = res["aggregates"]
                assert aggs["rpm_max"] == 12500
                assert aggs["rpm_avg"] == 11500
                assert aggs["water_temp_max"] == 87.0
                # 80 is already km/h — the m/s -> km/h conversion only kicks in below 50.
                assert aggs["speed_max_kmh"] == 80.0

                assert aggs["g_lateral_max"] == 1.5
                assert aggs["g_braking_max"] == 2.1
                assert aggs["battery_voltage_min"] == 12.3

                assert aggs["laps_count"] == 2
                assert aggs["best_lap_time"] == 50.5  # min(52.5, 50.5)
                assert aggs["duration_seconds"] == 600.0  # from metadata 0:10:00!
                assert aggs["session_date"] == "14/07/2026"
                assert aggs["circuit_name"] == "Le Mans"
                assert aggs["driver_name"] == "Test Driver"
