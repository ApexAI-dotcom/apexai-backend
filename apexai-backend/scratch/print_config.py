import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.config import settings
print("SUPABASE_URL:", settings.SUPABASE_URL)
print("SUPABASE_SERVICE_ROLE_KEY:", settings.SUPABASE_SERVICE_ROLE_KEY)
