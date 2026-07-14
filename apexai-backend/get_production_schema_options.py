import urllib.request
import json

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

headers = {
    "apikey": anon_key,
    "Authorization": f"Bearer {anon_key}",
    "Content-Type": "application/json"
}

print("Sending OPTIONS request to rest/v1/analyses...")
req = urllib.request.Request(
    f"{supabase_url}/rest/v1/analyses",
    headers=headers,
    method="OPTIONS"
)

try:
    with urllib.request.urlopen(req, timeout=10.0) as response:
        print(f"Status Code: {response.getcode()}")
        resp_data = json.loads(response.read().decode('utf-8'))
        print("OPTIONS Response:")
        print(json.dumps(resp_data, indent=2))
except Exception as e:
    print(f"Failed to fetch OPTIONS response: {e}")
    # Also try to check if GET /rest/v1 works with a single apikey header
    print("\nTrying GET /rest/v1 without slash and without Authorization header...")
    req_get = urllib.request.Request(
        f"{supabase_url}/rest/v1/",
        headers=headers,
        method="GET"
    )
    try:
        with urllib.request.urlopen(req_get, timeout=10.0) as response:
            print(f"GET Status Code: {response.getcode()}")
            schema = json.loads(response.read().decode('utf-8'))
            definitions = schema.get("definitions", {})
            print("Tables defined in Supabase:")
            print(list(definitions.keys()))
            print("\nProperties of kart_profiles:")
            print(list(definitions.get("kart_profiles", {}).get("properties", {}).keys()))
    except Exception as ex:
        print(f"Failed GET /rest/v1: {ex}")
