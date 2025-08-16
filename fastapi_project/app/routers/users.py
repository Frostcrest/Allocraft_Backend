"""
Users Router

Beginner guide:
- Admin-only endpoints for listing and managing users.
- Use /auth/register or /users (admin) to create accounts.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import schemas, crud, models
from ..database import get_db
from ..dependencies import require_role

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=list[schemas.UserRead] | schemas.UserRead)
def admin_create_user(user: schemas.UserCreate, db: Session = Depends(get_db), current_user: models.User = Depends(require_role("admin"))):
    """Create a new user (admin only).
    Mirrors /auth/register but gated by admin role, returning the created user.
    """
    if crud.get_user_by_username(db, user.username) or crud.get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Username or email already registered")
    db_user = crud.create_user(db, user)
    return db_user


@router.get("/", response_model=list[schemas.UserRead])
def list_users(db: Session = Depends(get_db), current_user: models.User = Depends(require_role("admin"))):
    return crud.list_users(db)


@router.put("/{user_id}", response_model=schemas.UserRead)
def admin_update_user(user_id: int, update: schemas.UserUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(require_role("admin"))):
    return crud.update_user(db, user_id, update)


@router.delete("/{user_id}")
def admin_delete_user(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(require_role("admin"))):
    success = crud.delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "User deleted"}
