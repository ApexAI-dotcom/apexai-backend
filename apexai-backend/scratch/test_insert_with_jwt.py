import sys
import uuid
from supabase import create_client

supabase_url = "https://vlqpljewmujlnxjuqetv.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZscXBsamV3bXVqbG54anVxZXR2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njg5MTcxOTAsImV4cCI6MjA4NDQ5MzE5MH0.K6m93Z78lPa70-0h6rY0tllkzYquMVAPERyijOzckxI"

client = create_client(supabase_url, anon_key)

# Sign up a temporary user to get a valid JWT
email = f"test_{uuid.uuid4()}@apexai.com"
password = "TestPassword123!"

print(f"Signing up temp user: {email}")
try:
    auth_res = client.auth.sign_up({"email": email, "password": password})
    user = auth_res.user
    session = auth_res.session
    if session:
        jwt = session.access_token
        print("Logged in successfully! JWT obtained.")
        
        # Now query the table with the logged in client
        client.postgrest.auth(jwt)
        
        # Test kart_setups
        try:
            res = client.table("kart_setups").select("*").limit(1).execute()
            print("kart_setups query succeeded! Data:", res.data)
        except Exception as e:
            print("kart_setups query failed:", e)
            
        # Test circuits
        try:
            res = client.table("circuits").select("*").limit(1).execute()
            print("circuits query succeeded! Data:", res.data)
        except Exception as e:
            print("circuits query failed:", e)
    else:
        print("SignUp succeeded but no session returned.")
except Exception as e:
    print("Authentication/SignUp failed:", e)
