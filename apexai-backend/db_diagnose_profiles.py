from supabase import create_client

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

client = create_client(supabase_url, anon_key)

print("Checking 'profiles' table...")
try:
    res = client.table("profiles").select("*").limit(1).execute()
    print("Succeeded querying profiles table!")
    if res.data:
        print("Sample profile row:")
        print(res.data[0])
    else:
        print("Profiles table is empty.")
except Exception as e:
    print(f"Failed to query profiles table: {e}")
