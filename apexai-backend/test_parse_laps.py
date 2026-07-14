import os
import time
import urllib.request
import urllib.error

ref_path = r"C:\Users\Administrateur\Documents\Apex\csv1\4adria_ftest.csv"

if not os.path.exists(ref_path):
    print(f"File not found: {ref_path}")
    exit(1)

print(f"Found reference file: {ref_path}")
with open(ref_path, "rb") as f:
    csv_content = f.read()

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body_data = bytearray()
body_data.extend(f"--{boundary}\r\n".encode())
body_data.extend(b'Content-Disposition: form-data; name="file"; filename="4adria_ftest.csv"\r\n')
body_data.extend(b'Content-Type: text/csv\r\n\r\n')
body_data.extend(csv_content)
body_data.extend(b'\r\n')
body_data.extend(f"--{boundary}--\r\n".encode())

url = "https://apexai-backend-production-19d8.up.railway.app/api/v1/parse-laps"
headers = {
    "Content-Type": f"multipart/form-data; boundary={boundary}",
    "Content-Length": str(len(body_data))
}

print("Uploading CSV to parse-laps on production backend...")
start_time = time.time()
req = urllib.request.Request(
    url,
    data=body_data,
    headers=headers,
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=60.0) as response:
        print(f"Status Code: {response.getcode()}")
        resp_text = response.read().decode('utf-8')
        print(f"Response: {resp_text[:500]}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} - {e.reason}")
    print(f"Body: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Error occurred: {e}")
print(f"Elapsed time: {time.time() - start_time:.2f} seconds")
