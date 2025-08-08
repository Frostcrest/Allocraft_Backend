from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import schemas, crud, models
from app.database import get_db
from app.dependencies import require_role

router = APIRouter(prefix="/users", tags=["Users"])


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
