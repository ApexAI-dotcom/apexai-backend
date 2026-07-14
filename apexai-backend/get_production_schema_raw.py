import urllib.request

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

headers = {
    "apikey": anon_key,
    "Authorization": f"Bearer {anon_key}",
}

print("Sending OPTIONS request to rest/v1/kart_profiles...")
req = urllib.request.Request(
    f"{supabase_url}/rest/v1/kart_profiles",
    headers=headers,
    method="OPTIONS"
)

try:
    with urllib.request.urlopen(req, timeout=10.0) as response:
        print(f"Status Code: {response.getcode()}")
        print("Headers:")
        for k, v in response.getheaders():
            print(f"  {k}: {v}")
        body = response.read()
        print(f"Raw body length: {len(body)}")
        print(f"Raw body: {body.decode('utf-8')[:2000]}")
except Exception as e:
    print(f"Failed: {e}")
