import time
import urllib.request
import urllib.error
import json

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

signup_url = f"{supabase_url}/auth/v1/signup"
headers = {
    "apikey": anon_key,
    "Content-Type": "application/json"
}
data = {
    "email": f"test_apexai_{int(time.time())}@example.com",
    "password": "TestPassword123!"
}

print("Signing up a test user...")
req = urllib.request.Request(
    signup_url,
    data=json.dumps(data).encode("utf-8"),
    headers=headers,
    method="POST"
)

jwt_token = None
try:
    with urllib.request.urlopen(req, timeout=10.0) as response:
        resp_body = response.read().decode('utf-8')
        resp_data = json.loads(resp_body)
        print("Response data keys:", list(resp_data.keys()))
        if "session" in resp_data:
            jwt_token = resp_data["session"].get("access_token")
        else:
            jwt_token = resp_data.get("access_token")
        print("jwt_token:", jwt_token)
        print("Success! User signed up.")
except Exception as e:
    print("Signup failed:", e)

if not jwt_token:
    print("No JWT token. Exiting.")
    exit(1)

# Now inspect tables using GET schema with API key and Authorization
for table in ['kart_setups', 'circuits']:
    table_headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {jwt_token}",
        "Accept": "application/vnd.pgrst.object+json" # request OpenAPI schema for the table or structure
    }
    # Let's do a SELECT query to see columns
    table_url = f"{supabase_url}/rest/v1/{table}?select=*&limit=1"
    req_table = urllib.request.Request(table_url, headers=table_headers, method="GET")
    try:
        with urllib.request.urlopen(req_table, timeout=10.0) as response:
            print(f"=== {table} columns ===")
            resp_body = response.read().decode('utf-8')
            print("Response:", resp_body)
    except urllib.error.HTTPError as e:
        print(f"Failed {table}: {e.code} - {e.reason}")
        print("Body:", e.read().decode('utf-8'))
    except Exception as e:
        print(f"Error {table}: {e}")
