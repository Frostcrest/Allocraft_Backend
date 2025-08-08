from app.utils.security import hash_password, verify_password
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime

from app import models, schemas
from app.services.price_service import (
    fetch_latest_price,
    fetch_yf_price,
    fetch_option_contract_price,
    fetch_ticker_info,
)

def get_ticker_by_symbol(db: Session, symbol: str):
    """
    Retrieve a ticker by its symbol.
    """
    return db.query(models.Ticker).filter(models.Ticker.symbol == symbol).first()

def create_ticker(db: Session, symbol: str) -> models.Ticker:
    """
    Create and persist a new ticker by symbol.
    If it already exists, returns the existing ticker.
    """
    existing = get_ticker_by_symbol(db, symbol)
    if existing:
        return existing
    ticker_data = fetch_ticker_info(symbol)
    if not ticker_data or not ticker_data.get("symbol"):
        raise HTTPException(status_code=404, detail=f"Ticker '{symbol}' not found.")
    db_ticker = models.Ticker(**ticker_data)
    db.add(db_ticker)
    db.commit()
    db.refresh(db_ticker)
    return db_ticker

def get_tickers(db: Session, skip: int = 0, limit: int = 100):
    """
    Retrieve a list of tickers with pagination.
    """
    return db.query(models.Ticker).offset(skip).limit(limit).all()

def get_ticker_by_id(db: Session, ticker_id: int):
    """
    Retrieve a ticker by its primary key ID.
    """
    return db.query(models.Ticker).filter(models.Ticker.id == ticker_id).first()

def delete_ticker(db: Session, ticker_id: int):
    """
    Delete a ticker by its ID. Returns True if deleted.
    """
    db_ticker = db.query(models.Ticker).filter(models.Ticker.id == ticker_id).first()
    if not db_ticker:
        return False
    db.delete(db_ticker)
    db.commit()
    return True

def create_price(db: Session, price: float, ticker_id: int, timestamp: datetime = None):
    """
    Create and persist a new price for a ticker.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    db_price = models.Price(
        price=price,
        ticker_id=ticker_id,
        timestamp=timestamp
    )
    db.add(db_price)
    db.commit()
    db.refresh(db_price)
    return db_price

def get_prices_for_ticker(db: Session, ticker_id: int, skip: int = 0, limit: int = 100):
    """
    Retrieve prices for a given ticker with pagination.
    """
    return (
        db.query(models.Price)
        .filter(models.Price.ticker_id == ticker_id)
        .order_by(models.Price.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_latest_price_for_ticker(db: Session, ticker_id: int):
    """
    Retrieve the latest price for a given ticker.
    """
    return (
        db.query(models.Price)
        .filter(models.Price.ticker_id == ticker_id)
        .order_by(models.Price.timestamp.desc())
        .first()
    )

def update_ticker_price(db: Session, symbol: str):
    """
    Fetch the latest price for a ticker and store it in the database.
    """
    ticker = get_ticker_by_symbol(db, symbol)
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker '{symbol}' not found.")
    latest_price = fetch_latest_price(symbol)
    if latest_price is None:
        raise HTTPException(status_code=400, detail=f"Could not fetch latest price for '{symbol}'.")
    return create_price(db, price=latest_price, ticker_id=ticker.id)

def get_option_contract_price(db: Session, symbol: str, contract_symbol: str):
    """
    Fetch the latest price for an option contract.
    """
    price = fetch_option_contract_price(symbol, contract_symbol)
    if price is None:
        raise HTTPException(status_code=404, detail=f"Option contract '{contract_symbol}' not found for '{symbol}'.")
    return price

def get_yf_price(db: Session, symbol: str):
    """
    Fetch the latest price for a ticker using yfinance.
    """
    price = fetch_yf_price(symbol)
    if price is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch yfinance price for '{symbol}'.")
    return price

# --- STOCK CRUD FUNCTIONS ---

def get_stocks(db: Session, refresh_prices: bool = False):
    """
    Retrieve all stock positions.
    """
    return db.query(models.Stock).all()

def create_stock(db: Session, stock: schemas.StockCreate):
    """
    Create and persist a new stock position.
    """
    db_stock = models.Stock(**stock.dict())
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock

def update_stock(db: Session, stock_id: int, stock: schemas.StockCreate):
    """
    Update an existing stock position.
    """
    db_stock = db.query(models.Stock).filter(models.Stock.id == stock_id).first()
    if not db_stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    for key, value in stock.dict().items():
        setattr(db_stock, key, value)
    db.commit()
    db.refresh(db_stock)
    return db_stock

def delete_stock(db: Session, stock_id: int):
    """
    Delete a stock position by its ID.
    """
    db_stock = db.query(models.Stock).filter(models.Stock.id == stock_id).first()
    if not db_stock:
        return False
    db.delete(db_stock)
    db.commit()
    return True

# --- OPTION CRUD FUNCTIONS ---

def get_options(db: Session):
    """
    Retrieve all option contracts.
    """
    return db.query(models.Option).all()

def create_option(db: Session, option: schemas.OptionCreate):
    """
    Create and persist a new option contract.
    """
    db_option = models.Option(**option.dict())
    db.add(db_option)
    db.commit()
    db.refresh(db_option)
    return db_option

def update_option(db: Session, option_id: int, option: schemas.OptionCreate):
    """
    Update an existing option contract.
    """
    db_option = db.query(models.Option).filter(models.Option.id == option_id).first()
    if not db_option:
        raise HTTPException(status_code=404, detail="Option not found")
    for key, value in option.dict().items():
        setattr(db_option, key, value)
    db.commit()
    db.refresh(db_option)
    return db_option

def delete_option(db: Session, option_id: int):
    """
    Delete an option contract by its ID.
    """
    db_option = db.query(models.Option).filter(models.Option.id == option_id).first()
    if not db_option:
        return False
    db.delete(db_option)
    db.commit()
    return True

# --- WHEEL STRATEGY CRUD FUNCTIONS ---

def get_wheels(db: Session):
    """
    Retrieve all wheel strategies.
    """
    return db.query(models.WheelStrategy).all()

def create_wheel(db: Session, wheel: schemas.WheelStrategyCreate):
    db_wheel = models.WheelStrategy(**wheel.dict())
    db.add(db_wheel)
    db.commit()
    db.refresh(db_wheel)
    return db_wheel

def update_wheel(db: Session, wheel_id: int, wheel: schemas.WheelStrategyCreate):
    db_wheel = db.query(models.WheelStrategy).filter(models.WheelStrategy.id == wheel_id).first()
    if not db_wheel:
        raise HTTPException(status_code=404, detail="Wheel strategy not found")
    for key, value in wheel.dict().items():
        setattr(db_wheel, key, value)
    db.commit()
    db.refresh(db_wheel)
    return db_wheel

def delete_wheel(db: Session, wheel_id: int):
    """
    Delete a wheel strategy by its ID.
    """
    db_wheel = db.query(models.WheelStrategy).filter(models.WheelStrategy.id == wheel_id).first()
    if not db_wheel:
        return False
    db.delete(db_wheel)
    db.commit()
    return True

# --- USER CRUD FUNCTIONS ---

def get_user_by_username(db: Session, username: str):
    """
    Retrieve a user by their username.
    """
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_email(db: Session, email: str):
    """
    Retrieve a user by their email.
    """
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    """
    Create a new user with hashed password.
    """
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        is_active=True,
        roles="user"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, username: str, password: str):
    """
    Authenticate a user by username and password.
    Returns the user if authentication is successful, else None.
    """
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def user_has_role(user: models.User, role: str) -> bool:
    """
    Check if the user has a specific role.
    """
    if not user or not user.roles:
        return False
    return role in [r.strip() for r in user.roles.split(",")]

# --- USER ADMIN FUNCTIONS ---

def list_users(db: Session):
    return db.query(models.User).all()

def update_user(db: Session, user_id: int, update: schemas.UserUpdate):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Uniqueness checks for username/email if changing
    if update.username and update.username != user.username:
        if get_user_by_username(db, update.username):
            raise HTTPException(status_code=400, detail="Username already in use")
        user.username = update.username
    if update.email and update.email != user.email:
        if get_user_by_email(db, update.email):
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = update.email
    if update.password:
        user.hashed_password = hash_password(update.password)
    if update.is_active is not None:
        user.is_active = update.is_active
    if update.roles is not None:
        user.roles = update.roles

    db.commit()
    db.refresh(user)
    return user

def delete_user(db: Session, user_id: int) -> bool:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True