from supabase import create_client

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

client = create_client(supabase_url, anon_key)

row = {
    "user_id": "00000000-0000-0000-0000-000000000000",
    "tires_laps_current": 0,
    "chain_hours_current": 0.0,
}

try:
    res = client.table("kart_profiles").insert(row).execute()
    print("Columns exist! Insert attempted.")
except Exception as e:
    print(f"Insert failed: {e}")
