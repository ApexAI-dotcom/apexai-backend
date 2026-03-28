import pandas as pd
import hashlib
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from src.core.data_loader import _detect_format, _parse_with_pandas, _extract_beacon_markers

logger = logging.getLogger(__name__)

def compute_file_signature(filepath: str, metadata: Dict[str, Any]) -> str:
    """
    Computes a unique SHA256 signature for the file to prevent duplicate imports.
    Combines file contents hash with key metadata.
    """
    try:
        # Hash the file contents
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        file_hash = sha256_hash.hexdigest()
        
        # Combine with metadata that identifies the session uniquely
        # e.g., Venue, Date, Time, Duration
        meta_str = f"{metadata.get('Venue', '')}_{metadata.get('Log Date', '')}_{metadata.get('Log Time', '')}_{metadata.get('Duration', '')}"
        
        final_hash = hashlib.sha256((file_hash + "|" + meta_str).encode('utf-8')).hexdigest()
        return final_hash
    except Exception as e:
        logger.error(f"Error computing file signature: {e}")
        # Fallback to random or basic hash if file read fails (should not happen normally)
        import uuid
        return str(uuid.uuid4())

def extract_motec_metadata(filepath: str) -> Dict[str, str]:
    """
    Extracts header metadata typically found in AiM/MoTeC CSVs.
    Returns a dictionary of Key-Value pairs.
    """
    metadata = {}
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= 15: # Headers are usually in the first 15 lines
                    break
                # Example: "Venue","Le Mans"
                if line.startswith('"') and '","' in line:
                    parts = line.strip().split('","')
                    if len(parts) >= 2:
                        key = parts[0].strip('"')
                        val = parts[1].strip('"')
                        metadata[key] = val
    except Exception as e:
        logger.warning(f"Could not extract metadata: {e}")
    return metadata

def parse_kart_mechanical(filepath: str) -> Dict[str, Any]:
    """
    Parses a CSV telemetry file completely to extract ONLY mechanical aggregates
    like max RPM, max temperatures, speed, lateral G, braking G, and battery.
    No downsampling is performed, making it highly accurate for min/max/aggregates.
    """
    
    result = {
        "success": False,
        "signature": None,
        "aggregates": {},
        "metadata": {},
        "error": None
    }
    
    if not Path(filepath).exists():
        result["error"] = "File not found."
        return result
        
    try:
        # 1. Read metadata from header
        metadata = extract_motec_metadata(filepath)
        result["metadata"] = metadata
        
        # 2. Compute file signature
        signature = compute_file_signature(filepath, metadata)
        result["signature"] = signature
        
        # 3. Detect format and load with pandas
        skiprows = _detect_format(filepath)
        
        # Try UTF-8 first, then Latin-1
        df = _parse_with_pandas(filepath, skiprows, 'utf-8')
        if df is None or len(df) == 0:
            df = _parse_with_pandas(filepath, skiprows, 'latin-1')
        
        if df is None or len(df) == 0:
            result["error"] = "Failed to parse CSV file."
            return result
        
        # Compute aggregates without downsampling
        df.columns = [c.lower().strip() for c in df.columns]
        
        # Initialize aggregates
        aggs = {
            "rpm_max": None,
            "rpm_avg": None,
            "water_temp_max": None,
            "water_temp_avg": None,
            "exhaust_temp_max": None,
            "exhaust_temp_avg": None,
            "speed_max_kmh": None,
            "g_lateral_max": None,
            "g_braking_max": None,
            "battery_voltage_avg": None,
            "battery_voltage_min": None,
            "duration_seconds": 0.0,
            "duration_hours": 0.0,
            "laps_count": 0,
            "best_lap_time": None,
            "session_date": metadata.get("Log Date", None),
            "circuit_name": metadata.get("Venue", None),
            "driver_name": metadata.get("Driver", None)
        }
        
        # Process beacon markers for laps and best lap time
        beacons = _extract_beacon_markers(filepath)
        if beacons and len(beacons) > 1:
            aggs["laps_count"] = len(beacons) - 1
            lap_times = [beacons[i] - beacons[i-1] for i in range(1, len(beacons))]
            valid_lap_times = [t for t in lap_times if t > 10.0] # ignore very short spurious laps
            if valid_lap_times:
                aggs["best_lap_time"] = min(valid_lap_times)
        
        def get_series(df: pd.DataFrame, possible_names: list) -> Optional[pd.Series]:
            for name in possible_names:
                matches = [c for c in df.columns if name in c]
                for match in matches:
                    s = pd.to_numeric(df[match], errors='coerce').dropna()
                    if not s.empty:
                        return s
            return None
            
        # Time and Duration
        time_series = get_series(df, ['time', 't', 'timestamp'])
        if time_series is not None and len(time_series) > 0:
            max_t = time_series.max()
            min_t = time_series.min()
            # If > 50000 likely ms
            if max_t > 50000:
                duration_s = (max_t - min_t) / 1000.0
            else:
                duration_s = max_t - min_t
            aggs["duration_seconds"] = float(duration_s)
            aggs["duration_hours"] = float(duration_s / 3600.0)
            
            # Use metadata Duration if specified
            # e.g., "0:14:23.000"
            if metadata.get("Duration"):
                dur_str = metadata.get("Duration")
                if ":" in dur_str:
                    parts = dur_str.split(":")
                    if len(parts) == 3:
                        h = float(parts[0])
                        m = float(parts[1])
                        s = float(parts[2])
                        computed_s = h*3600 + m*60 + s
                        aggs["duration_seconds"] = computed_s
                        aggs["duration_hours"] = computed_s / 3600.0
            
        # RPM
        rpm_series = get_series(df, ['rpm', 'engine'])
        if rpm_series is not None:
            aggs["rpm_max"] = float(rpm_series.max())
            aggs["rpm_avg"] = float(rpm_series.mean())
            
        # Water Temp
        water_series = get_series(df, ['water', 'h2o', 'coolant'])
        if water_series is not None:
            aggs["water_temp_max"] = float(water_series.max())
            aggs["water_temp_avg"] = float(water_series.mean())
            
        # Exhaust Temp
        exhaust_series = get_series(df, ['exhaust', 'egt'])
        if exhaust_series is not None:
            aggs["exhaust_temp_max"] = float(exhaust_series.max())
            aggs["exhaust_temp_avg"] = float(exhaust_series.mean())
            
        # Speed
        speed_series = get_series(df, ['speed', 'vel', 'spd', 'vitesse'])
        if speed_series is not None:
            sp_max = float(speed_series.max())
            if sp_max < 50:
                sp_max *= 3.6 # assumption: m/s -> km/h
            aggs["speed_max_kmh"] = sp_max
            
        # Lateral G
        latg_series = get_series(df, ['lat_g', 'lateral', 'ay', 'accel_lat', 'gps latacc'])
        if latg_series is not None:
            aggs["g_lateral_max"] = float(latg_series.abs().max())
            
        # Braking / Longitudinal G
        longg_series = get_series(df, ['lon_g', 'longitudinal', 'ax', 'accel_lon', 'gps lonacc'])
        if longg_series is not None:
            # Braking is usually negative acceleration, so min()
            val1 = float(longg_series.min())
            val2 = float(longg_series.max())
            # We want the max absolute braking force
            aggs["g_braking_max"] = float(max(abs(val1), abs(val2)))
            
        # Battery Voltage
        batt_series = get_series(df, ['batt', 'volt', 'vbat', 'int batt voltage'])
        if batt_series is not None:
            aggs["battery_voltage_avg"] = float(batt_series.mean())
            aggs["battery_voltage_min"] = float(batt_series.min())
            
        result["aggregates"] = aggs
        result["success"] = True
        
    except Exception as e:
        logger.exception(f"Error parse_kart_mechanical: {e}")
        result["error"] = str(e)
        
    return result
