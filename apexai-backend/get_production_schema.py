import urllib.request
import json

url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

headers = {
    "apikey": anon_key,
    "Authorization": f"Bearer {anon_key}",
    "Content-Type": "application/json"
}

print("Fetching OpenAPI schema from Supabase REST API...")
req = urllib.request.Request(
    f"{url}/rest/v1/",
    headers=headers,
    method="GET"
)

try:
    with urllib.request.urlopen(req, timeout=15.0) as response:
        schema = json.loads(response.read().decode('utf-8'))
        definitions = schema.get("definitions", {})
        analyses_def = definitions.get("analyses", {})
        print("Analyses Table Definition in Production:")
        print(json.dumps(analyses_def, indent=2))
except Exception as e:
    print(f"Error fetching schema: {e}")
