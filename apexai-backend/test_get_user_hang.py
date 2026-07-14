import os
import time
from supabase import create_client

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
# Let's try anon key first
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

print("Initializing supabase client...")
client = create_client(supabase_url, anon_key)

print("Calling get_user with invalid JWT...")
start = time.time()
try:
    user = client.auth.get_user(jwt="invalid_jwt_token_here")
    print(f"Succeeded! User: {user}")
except Exception as e:
    print(f"Failed with exception (expected): {e}")
print(f"Duration: {time.time() - start:.2f} seconds")
