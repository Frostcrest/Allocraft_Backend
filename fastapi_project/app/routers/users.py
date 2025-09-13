"""
Users Router

Beginner guide:
- Admin-only endpoints for listing and managing users.
- Use /auth/register or /users (admin) to create accounts.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import schemas, crud, models
from ..services.users_service import UsersService
from ..database import get_db
from ..dependencies import require_role

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=list[schemas.UserRead] | schemas.UserRead)
def admin_create_user(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_role("admin"))):
    """Create a new user (admin only)."""
    try:
        return UsersService.admin_create_user(user, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


@router.get("/", response_model=list[schemas.UserRead])
def list_users(db: Session = Depends(get_db), current_user: models.User = Depends(require_role("admin"))):
    try:
        return UsersService.list_users(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list users: {str(e)}")


@router.put("/{user_id}", response_model=schemas.UserRead)
def admin_update_user(user_id: int, update: schemas.UserUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_role("admin"))):
    try:
        updated = UsersService.admin_update_user(user_id, update, db)
        if not updated:
            raise HTTPException(status_code=404, detail="User not found")
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update user: {str(e)}")


@router.delete("/{user_id}")
def admin_delete_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_role("admin"))):
    try:
        success = UsersService.admin_delete_user(user_id, db)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")
        return {"detail": "User deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")
