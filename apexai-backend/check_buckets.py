import json
from supabase import create_client

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

client = create_client(supabase_url, anon_key)

print("Listing storage buckets...")
try:
    buckets = client.storage.list_buckets()
    print("Buckets found:")
    for b in buckets:
        print(f"  ID: {b.id}, Name: {b.name}, Public: {b.public}")
except Exception as e:
    print(f"Failed to list buckets: {e}")
