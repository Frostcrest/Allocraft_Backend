from fastapi import Depends, HTTPException, status
from app.routers.auth import get_current_user
from app import models

def require_authenticated_user(current_user: models.User = Depends(get_current_user)):
    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return current_user

def require_role(role: str):
    def role_checker(current_user: models.User = Depends(get_current_user)):
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