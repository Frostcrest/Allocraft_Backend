from sqlalchemy.orm import Session
from .. import schemas, crud, models
from typing import List, Optional

class UsersService:
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
        return crud.get_user_by_id(db, user_id)
    @staticmethod
    def admin_create_user(user: schemas.UserCreate, db: Session) -> models.User:
        if crud.get_user_by_username(db, user.username) or crud.get_user_by_email(db, user.email):
            raise ValueError("Username or email already registered")
        return crud.create_user(db, user)

    @staticmethod
    def list_users(db: Session) -> List[models.User]:
        return crud.list_users(db)

    @staticmethod
    def admin_update_user(user_id: int, update: schemas.UserUpdate, db: Session) -> Optional[models.User]:
        return crud.update_user(db, user_id, update)

    @staticmethod
    def admin_delete_user(user_id: int, db: Session) -> bool:
        return crud.delete_user(db, user_id)
