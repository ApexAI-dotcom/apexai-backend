from supabase import create_client

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

client = create_client(supabase_url, anon_key)

print("Checking 'analysis-plots' bucket...")
try:
    bucket = client.storage.get_bucket("analysis-plots")
    print(f"Bucket 'analysis-plots' exists! ID: {bucket.id}, Public: {bucket.public}")
except Exception as e:
    print(f"Bucket 'analysis-plots' check failed: {e}")

print("\nChecking 'avatars' bucket...")
try:
    bucket = client.storage.get_bucket("avatars")
    print(f"Bucket 'avatars' exists! ID: {bucket.id}, Public: {bucket.public}")
except Exception as e:
    print(f"Bucket 'avatars' check failed: {e}")
