from twelvedata import TDClient
from fastapi import HTTPException
from sqlalchemy.orm import Session
from . import models, schemas

from app.schemas import PositionCreate

# Positions CRUD

def get_positions(db: Session):
    return db.query(models.Position).all()

def create_position(db: Session, position: PositionCreate):
    db_position = models.Position(
        symbol=position.symbol,
        quantity=position.quantity,
        average_price=position.average_price
    )
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return db_position

def update_position(db: Session, position_id: int, position_data: PositionCreate):
    db_position = db.query(models.Position).filter(models.Position.id == position_id).first()
    if db_position:
        db_position.symbol = position_data.symbol
        db_position.quantity = position_data.quantity
        db_position.average_price = position_data.average_price
        db.commit()
        db.refresh(db_position)
    return db_position

def delete_position(db: Session, id: int):
    pos = db.query(models.Position).filter(models.Position.id == id).first()
    if pos:
        db.delete(pos)
        db.commit()
        return True
    return False

# Option Positions CRUD

def get_option_positions(db: Session):
    return db.query(models.OptionPosition).all()

def create_option_position(db: Session, option_position: models.OptionPosition):
    db.add(option_position)
    db.commit()
    db.refresh(option_position)
    return option_position

def update_option_position(db: Session, id: int, new_data: dict):
    opt = db.query(models.OptionPosition).filter(models.OptionPosition.id == id).first()
    if not opt:
        raise HTTPException(status_code=404, detail="Option position not found")
    for key, value in new_data.items():
        setattr(opt, key, value)
    db.commit()
    db.refresh(opt)
    return opt

def delete_option_position(db: Session, id: int):
    opt = db.query(models.OptionPosition).filter(models.OptionPosition.id == id).first()
    if opt:
        db.delete(opt)
        db.commit()
        return True
    return False

# --- Ticker CRUD ---
TD_API_KEY = "59076e2930e5489796d3f74ea7082959"
td = TDClient(apikey=TD_API_KEY)

def fetch_ticker_info(symbol: str) -> dict:
    """Fetch ticker info from Twelve Data API."""
    try:
        data = td.quote(symbol=symbol).as_json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch data from Twelve Data: {str(e)}")
    if not data or "code" in data:
        raise HTTPException(status_code=404, detail=f"Ticker '{symbol}' not found.")
    return {
        "symbol": data.get("symbol"),
        "name": data.get("name"),
        "last_price": data.get("close"),
        "change": data.get("change"),
        "change_percent": data.get("percent_change"),
        "volume": data.get("volume"),
        "market_cap": None,
        "timestamp": data.get("datetime"),
    }

def create_ticker(db: Session, symbol: str) -> models.Ticker:
    """Create and persist a new ticker by symbol."""
    existing = get_ticker_by_symbol(db, symbol)
    if existing:
        return existing
    ticker_data = fetch_ticker_info(symbol)
    db_ticker = models.Ticker(**ticker_data)
    db.add(db_ticker)
    db.commit()
    db.refresh(db_ticker)
    return db_ticker

def get_ticker_by_symbol(db: Session, symbol: str):
    """Get a ticker by its symbol."""
    return db.query(models.Ticker).filter(models.Ticker.symbol == symbol).first()

def get_ticker_by_id(db: Session, ticker_id: int):
    """Get a ticker by its ID."""
    ticker = db.query(models.Ticker).filter(models.Ticker.id == ticker_id).first()
    if not ticker:
        raise HTTPException(status_code=404, detail="Ticker not found.")
    return ticker

def get_tickers(db: Session):
    """Return all tickers."""
    return db.query(models.Ticker).all()

def delete_ticker(db: Session, ticker_id: int):
    """Delete a ticker by ID."""
    ticker = db.query(models.Ticker).filter(models.Ticker.id == ticker_id).first()
    if ticker:
        db.delete(ticker)
        db.commit()
        return True
    raise HTTPException(status_code=404, detail="Ticker not found.")
