import os
from functools import wraps
from fastapi import HTTPException, status

NEVA_ADMIN_TOKEN = os.getenv("NEVA_ADMIN_TOKEN", "admin123")
NEVA_AGENT_TOKEN = os.getenv("NEVA_AGENT_TOKEN", "agent123")

def get_token_role(token):
    if token == NEVA_ADMIN_TOKEN: return "admin"
    if token == NEVA_AGENT_TOKEN: return "agent"
    return None

def require_auth(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper

def require_admin(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return wrapper
