from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from app import schemas, crud, models
from app.database import get_db
from app.utils.security import verify_password
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-dev")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
DISABLE_AUTH = os.getenv("DISABLE_AUTH", "1") in ("1", "true", "True")

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    if DISABLE_AUTH:
        # Return a faux active admin user for local development/testing
        return models.User(username="local", email="local@example.com", hashed_password="", is_active=True, roles="admin")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=schemas.UserRead)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if crud.get_user_by_username(db, user.username) or crud.get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Username or email already registered")
    db_user = crud.create_user(db, user)
    return db_user

@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = create_access_token(data={"sub": user.username, "roles": user.roles})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UserRead)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    return current_user