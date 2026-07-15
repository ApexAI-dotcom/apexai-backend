import sys
from supabase import create_client

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

client = create_client(supabase_url, anon_key)

try:
    # Postgrest has a root GET which returns OpenAPI
    # In supabase-py, client.postgrest is the PostgrestClient
    res = client.postgrest.get("/").execute()
    # Wait, client.postgrest.get is not a standard method, but we can do a request or check:
    print("Postgrest client keys:")
    # Let's inspect the tables via client table names
    # Postgrest schema description is at client.postgrest.session or via custom query
except Exception as e:
    print("Error:", e)
