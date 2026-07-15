import urllib.request
import json

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"
headers = {
    "apikey": anon_key,
    "Authorization": f"Bearer {anon_key}",
}

for table in ['kart_setups', 'circuits']:
    req = urllib.request.Request(f"{supabase_url}/rest/v1/{table}?select=*&limit=1", headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=10.0) as response:
            print(f"=== {table} ===")
            body = response.read().decode('utf-8')
            data = json.loads(body)
            if data and len(data) > 0:
                for col in data[0].keys():
                    print(f"  {col}")
            else:
                print("  No records found to determine columns, but request succeeded.")
    except Exception as e:
        print(f"Failed {table}: {e}")
