import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from src.analysis.geometry import calculate_trajectory_geometry, detect_corners, detect_laps
    from src.analysis.performance_metrics import analyze_corner_performance
    from src.analysis.scoring import calculate_performance_score
    from src.analysis.coaching import generate_coaching_advice
    
    print("✓ Successfully imported all analysis modules.")
    
    # 1. Simulate track data (3 laps)
    n_pts = 3000
    t = np.linspace(0, 300, n_pts)
    radius = 50
    # Simulate slightly changing laps
    lap_offsets = np.repeat(np.array([0, 0.0001, 0.0002]), 1000)
    lat = 45.0 + ((radius / 111000) * np.sin(t / 10)) + lap_offsets
    lon = 5.0 + ((radius / (111000 * np.cos(np.radians(45.0)))) * np.cos(t / 10))
    
    df = pd.DataFrame({
        "time": t,
        "latitude_smooth": lat,
        "longitude_smooth": lon,
        "speed": np.full(n_pts, 60.0) + np.sin(t/5) * 10 # Speed oscillates between 50 and 70
    })
    
    print("✓ Data generation complete.")
    
    # 2. Pipeline Execution
    print("> Running geometry pipeline...")
    df = calculate_trajectory_geometry(df)
    df = detect_laps(df)
    df["lateral_g"] = np.sin(t/3) * 1.5 # Inject pseudo lateral G
    df = detect_corners(df)
    
    print("> Running scoring & performance pipeline...")
    if 'corners' in df.attrs and df.attrs['corners'].get('corner_details'):
        corner_details = df.attrs['corners']['corner_details']
        
        # Performance
        corner_analysis = []
        for corner in corner_details:
            analysis = analyze_corner_performance(df, corner)
            # Merge metrics back into corner payload
            corner['score'] = analysis['score']
            corner['grade'] = analysis['grade']
            corner['metrics'] = analysis['metrics']
            corner_analysis.append(analysis)
            
        # Scoring
        score_data = calculate_performance_score(df, corner_details)
        print(f"  Overall Score: {score_data['overall_score']}")
        
        # Coaching
        advice = generate_coaching_advice(df, corner_details, score_data, corner_analysis, laps_analyzed=3)
        print(f"  Generated {len(advice)} coaching advices.")
        
        print("🎉 Full pipeline test passed successfully!")
    else:
        print("❌ Pipeline failed to detect corners or attach metadata.")
        sys.exit(1)
        
    sys.exit(0)
    
except Exception as e:
    import traceback
    print("❌ Error testing pipeline:")
    traceback.print_exc()
    sys.exit(1)
