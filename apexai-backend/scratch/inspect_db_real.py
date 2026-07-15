import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.kart_service import supabase

if not supabase:
    print("Supabase not initialized! Check environment variables.")
    sys.exit(1)

print("Supabase Client initialized.")

for table in ['kart_setups', 'circuits']:
    try:
        res = supabase.table(table).select("*").limit(1).execute()
        print(f"Table '{table}' exists! Columns/Data:")
        print(res.data)
    except Exception as e:
        print(f"Error querying '{table}': {e}")
