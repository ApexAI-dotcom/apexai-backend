import time
import urllib.request
import urllib.error

base_url = "https://apexai-backend-production-19d8.up.railway.app"

endpoints = [
    ("/health", "GET"),
    ("/api/auth/debug", "GET"),
    ("/api/analyses", "GET"),
]

for endpoint, method in endpoints:
    url = f"{base_url}{endpoint}"
    print(f"Testing {method} {url}...")
    start_time = time.time()
    req = urllib.request.Request(
        url,
        method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=10.0) as response:
            print(f"Status Code: {response.getcode()}")
            print(f"Body: {response.read().decode('utf-8')[:200]}")
            print(f"Elapsed time: {time.time() - start_time:.2f} seconds")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        print(f"Body: {e.read().decode('utf-8')[:200]}")
        print(f"Elapsed time: {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"Error occurred: {e}")
        print(f"Elapsed time: {time.time() - start_time:.2f} seconds")
    print("-" * 50)
