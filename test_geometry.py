import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.abspath("src"))

try:
    from analysis.geometry import calculate_trajectory_geometry, detect_corners, detect_laps
    print("✓ Successfully imported modules from geometry.py")
    
    # Create mock dataframe
    n_pts = 1000
    t = np.linspace(0, 100, n_pts)
    # create a circular track
    radius = 50
    lat = 45.0 + (radius / 111000) * np.sin(t / 10)
    lon = 5.0 + (radius / (111000 * np.cos(np.radians(45.0)))) * np.cos(t / 10)
    
    df = pd.DataFrame({
        "time": t,
        "latitude_smooth": lat,
        "longitude_smooth": lon,
        "speed": np.full(n_pts, 50.0) # 50 km/h constant
    })
    
    df_geom = calculate_trajectory_geometry(df)
    print("✓ calculate_trajectory_geometry passed")
    
    df_laps = detect_laps(df_geom)
    print(f"✓ detect_laps passed. Found laps: {df_laps['lap_number'].nunique()}")
    
    # Fake some lateral G peaks to test detect_corners
    df_laps["lateral_g"] = np.sin(t) * 1.5 # Oscillating G
    
    df_corners = detect_corners(df_laps)
    print(f"✓ detect_corners passed.")
    if 'corners' in df_corners.attrs:
        print(f"  Found {df_corners.attrs['corners'].get('total_corners', 0)} corners.")
    else:
        print("  WARNING: 'corners' attr missing from output.")
        
    print("🎉 All basic geometry tests passed.")
    sys.exit(0)
except Exception as e:
    import traceback
    print(f"❌ Error testing geometry.py:")
    traceback.print_exc()
    sys.exit(1)
