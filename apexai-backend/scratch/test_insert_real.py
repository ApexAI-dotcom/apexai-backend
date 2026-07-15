import sys
from supabase import create_client

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

client = create_client(supabase_url, anon_key)

test_row = {
    "user_id": "00000000-0000-0000-0000-000000000000",
}

print("Attempting to insert into singular 'circuit'...")
try:
    res = client.table("circuit").insert({"name": "Test Circuit"}).execute()
    print("Success! Table 'circuit' exists. Row:", res.data)
except Exception as e:
    print("Error details for 'circuit':", str(e))

print("Attempting to insert into singular 'kart_setup'...")
try:
    res = client.table("kart_setup").insert(test_row).execute()
    print("Success! Table 'kart_setup' exists. Row:", res.data)
except Exception as e:
    print("Error details for 'kart_setup':", str(e))
