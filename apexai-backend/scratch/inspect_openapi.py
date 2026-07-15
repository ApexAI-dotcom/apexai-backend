import urllib.request
import json

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"
headers = {
    "apikey": anon_key,
    "Authorization": f"Bearer {anon_key}",
}

req = urllib.request.Request(f"{supabase_url}/rest/v1/", headers=headers, method='GET')
try:
    with urllib.request.urlopen(req, timeout=10.0) as response:
        body = response.read().decode('utf-8')
        schema = json.loads(body)
        definitions = schema.get('definitions', {})
        for table in ['kart_setups', 'circuits']:
            print(f"=== {table} ===")
            properties = definitions.get(table, {}).get('properties', {})
            for col, details in properties.items():
                print(f"  {col}: {details.get('type')} ({details.get('description') or ''})")
except Exception as e:
    print(f"Failed: {e}")
