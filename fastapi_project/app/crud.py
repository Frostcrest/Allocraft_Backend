from twelvedata import TDClient
from fastapi import HTTPException
from sqlalchemy.orm import Session
from . import models, schemas


def create_position(db: Session, position: schemas.PositionCreate) -> models.Position:
    db_position = models.Position(**position.dict())
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return db_position

def get_positions(db: Session):
    return db.query(models.Position).all()

def delete_position(db: Session, position_id: int):
    pos = db.query(models.Position).filter(models.Position.id == position_id).first()
    if pos:
        db.delete(pos)
        db.commit()
        return True
    return False


# Replace with your actual Twelve Data API key
TD_API_KEY = "59076e2930e5489796d3f74ea7082959"
td = TDClient(apikey=TD_API_KEY)

def fetch_ticker_info(symbol: str) -> dict:
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
        "market_cap": None,  # Optional, not provided by Twelve Data
        "timestamp": data.get("datetime"),
    }

def create_ticker(db: Session, symbol: str) -> models.Ticker:
    # Check if ticker already exists to avoid duplicates
    existing = get_ticker_by_symbol(db, symbol)
    if existing:
        return existing

    # Fetch data from Twelve Data API
    ticker_data = fetch_ticker_info(symbol)

    # Create and persist the ticker
    db_ticker = models.Ticker(**ticker_data)
    db.add(db_ticker)
    db.commit()
    db.refresh(db_ticker)
    return db_ticker

def get_ticker_by_symbol(db: Session, symbol: str):
    return db.query(models.Ticker).filter(models.Ticker.symbol == symbol).first()

def delete_ticker(db: Session, ticker_id: int):
    ticker = db.query(models.Ticker).filter(models.Ticker.id == ticker_id).first()
    if ticker:
        db.delete(ticker)
        db.commit()
        return True
    return False
