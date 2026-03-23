from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request

def get_user_token_or_ip(request: Request) -> str:
    """Utilise le token JWT s'il est présent, sinon fallback sur l'IP."""
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth.replace("Bearer ", "").strip()
    return get_remote_address(request)

# Limiteur global par IP par défaut
limiter = Limiter(key_func=get_remote_address)
