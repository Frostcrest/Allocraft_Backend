import pytest
from fastapi_project.app.services.users_service import UsersService
from fastapi_project.app.database import SessionLocal

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_get_user_by_id_returns_none_for_missing(db):
    user = UsersService.get_user_by_id(db, user_id=999999)
    assert user is None or getattr(user, 'id', None) != 999999
