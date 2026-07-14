import json
from supabase import create_client

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

client = create_client(supabase_url, anon_key)

print("--- Case 1: Testing Backend Schema Columns ---")
# Backend columns: id (uuid), user_id (uuid), track_name, session_date, telemetry_data, ai_insights, lap_count
backend_row = {
    "user_id": "00000000-0000-0000-0000-000000000000",
    "track_name": "Test Track",
    "lap_count": 5,
    "ai_insights": {}
}

try:
    res = client.table("analyses").insert(backend_row).execute()
    print("Backend schema insert succeeded or bypassed schema validation (e.g. RLS fail). Result:")
    print(res)
except Exception as e:
    print(f"Backend schema insert failed: {e}")


print("\n--- Case 2: Testing Frontend Schema Columns ---")
# Frontend columns: id (text), user_id (uuid), score, grade, lap_time, best_lap_time, corners_detected, circuit_name, session_name, session_type
frontend_row = {
    "id": "test_id_123",
    "user_id": "00000000-0000-0000-0000-000000000000",
    "score": 80,
    "grade": "B",
    "lap_time": 45.5,
    "best_lap_time": 45.0,
    "corners_detected": 10,
    "circuit_name": "Circuit Test",
    "session_name": "Session Test"
}

try:
    res = client.table("analyses").insert(frontend_row).execute()
    print("Frontend schema insert succeeded or bypassed schema validation (e.g. RLS fail). Result:")
    print(res)
except Exception as e:
    print(f"Frontend schema insert failed: {e}")
