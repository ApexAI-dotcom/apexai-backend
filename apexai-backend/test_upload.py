import time
import urllib.request
import urllib.error
import json
import io

# Let's generate a valid CSV content with enough rows to pass all gates.
# From test_csv_robustness.py, a valid circuit session has multiple laps and coordinates.
# Let's build a simple dataset with 60 points representing a simple loop.
csv_lines = ["latitude,longitude,speed,time,lap_number"]
# Generate 100 points
for i in range(100):
    # Sinusoidal trajectory to simulate a loop
    lat = 45.0 + 0.001 * (i % 20)
    lon = 5.0 + 0.001 * (i // 20)
    speed = 60.0 + (i % 5)
    t = float(i) * 0.5
    # Let's simulate 3 laps
    lap = (i // 30) + 1
    csv_lines.append(f"{lat},{lon},{speed},{t},{lap}")

csv_content = "\n".join(csv_lines).encode("utf-8")

# Prepare multipart/form-data payload manually using standard library to avoid external dependencies
boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body = io.BytesIO()
body.write(f"--{boundary}\r\n".encode())
body.write(b'Content-Disposition: form-data; name="file"; filename="test_telemetry.csv"\r\n')
body.write(b'Content-Type: text/csv\r\n\r\n')
body.write(csv_content)
body.write(b'\r\n')
body.write(f"--{boundary}\r\n".encode())
body.write(b'Content-Disposition: form-data; name="track_condition"\r\n\r\n')
body.write(b'dry\r\n')
body.write(f"--{boundary}--\r\n".encode())

payload = body.getvalue()

url = "https://apexai-backend-production-19d8.up.railway.app/api/v1/analyze"
headers = {
    "Content-Type": f"multipart/form-data; boundary={boundary}",
    "Content-Length": str(len(payload))
}

print("Uploading CSV to production backend...")
start_time = time.time()
req = urllib.request.Request(
    url,
    data=payload,
    headers=headers,
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=30.0) as response:
        print(f"Status Code: {response.getcode()}")
        resp_text = response.read().decode('utf-8')
        print(f"Response: {resp_text[:500]}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} - {e.reason}")
    print(f"Body: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error occurred: {e}")
print(f"Elapsed time: {time.time() - start_time:.2f} seconds")
