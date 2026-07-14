import time
import urllib.request
import urllib.error
import json
import io

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"
api_url = "https://apexai-backend-production-19d8.up.railway.app"

# Let's try signing in a temporary user or signing up.
# Since we might not want to create garbage accounts, let's try to sign up with a random email first,
# and if it succeeds or fails, we will know. Or we can try to sign in with a random email/password.
# Actually, let's sign up a test account: test_apexai_diag@example.com / TestPass123!
signup_url = f"{supabase_url}/auth/v1/signup"
headers = {
    "apikey": anon_key,
    "Content-Type": "application/json"
}
data = {
    "email": f"test_apexai_{int(time.time())}@example.com",
    "password": "TestPassword123!"
}

jwt_token = None

print("Signing up a test user on Supabase...")
req = urllib.request.Request(
    signup_url,
    data=json.dumps(data).encode("utf-8"),
    headers=headers,
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=10.0) as response:
        resp_body = response.read().decode('utf-8')
        print(f"Response Body: {resp_body}")
        resp_data = json.loads(resp_body)
        jwt_token = resp_data.get("access_token")
        user_id = resp_data.get("user", {}).get("id") if resp_data.get("user") else None
        print(f"Signup successful! User ID: {user_id}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error on Signup: {e.code} - {e.reason}")
    print(f"Body: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error on Signup: {e}")

if not jwt_token:
    print("Failed to get JWT token. Exiting.")
    exit(1)

# Now, let's upload a CSV to the production API WITH the Authorization header!
ref_path = r"C:\Users\Administrateur\Documents\Apex\csv1\4adria_ftest.csv"
if not os.path.exists(ref_path):
    print(f"File not found: {ref_path}")
    exit(1)

with open(ref_path, "rb") as f:
    csv_content = f.read()

# Add a dummy comment to force cache miss and run the actual backend code!
altered_content = csv_content + f"\n# dummy_comment_{int(time.time())}\n".encode("utf-8")

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body_data = bytearray()
body_data.extend(f"--{boundary}\r\n".encode())
body_data.extend(b'Content-Disposition: form-data; name="file"; filename="4adria_ftest.csv"\r\n')
body_data.extend(b'Content-Type: text/csv\r\n\r\n')
body_data.extend(altered_content)
body_data.extend(b'\r\n')
body_data.extend(f"--{boundary}\r\n".encode())
body_data.extend(b'Content-Disposition: form-data; name="track_condition"\r\n\r\n')
body_data.extend(b'dry\r\n')
body_data.extend(f"--{boundary}--\r\n".encode())

upload_headers = {
    "Content-Type": f"multipart/form-data; boundary={boundary}",
    "Content-Length": str(len(body_data)),
    "Authorization": f"Bearer {jwt_token}"
}

print("Uploading CSV to production backend with Authorization header...")
start_time = time.time()
upload_req = urllib.request.Request(
    f"{api_url}/api/v1/analyze",
    data=body_data,
    headers=upload_headers,
    method="POST"
)

try:
    with urllib.request.urlopen(upload_req, timeout=120.0) as response:
        print(f"Status Code: {response.getcode()}")
        resp_text = response.read().decode('utf-8')
        print(f"Response: {resp_text[:500]}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} - {e.reason}")
    print(f"Body: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error occurred: {e}")
print(f"Elapsed time: {time.time() - start_time:.2f} seconds")
