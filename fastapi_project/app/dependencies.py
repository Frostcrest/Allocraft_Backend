"""
Auth Dependencies

Beginner guide:
- DISABLE_AUTH=1 (default in local dev) returns a fake admin user so you can try the app quickly.
- In production, you must be authenticated and have the required roles.
"""

from fastapi import Depends, HTTPException, status
from .routers.auth import get_current_user
from . import models
import os
from dotenv import load_dotenv

load_dotenv()
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "1") in ("1", "true", "True")

def require_authenticated_user(current_user: models.User = Depends(get_current_user)):
    if DISABLE_AUTH:
        # Return a faux active user for local development
        return models.User(username="local", email="local@example.com", hashed_password="", is_active=True, roles="admin")
    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return current_user

def require_role(role: str):
    def role_checker(current_user: models.User = Depends(get_current_user)):
        if DISABLE_AUTH:
            return models.User(username="local", email="local@example.com", hashed_password="", is_active=True, roles="admin")
        if not current_user or not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        roles = [r.strip() for r in (current_user.roles or "").split(",")]
        if role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have required role: {role}",
            )
        return current_user
    return role_checker