from twelvedata import TDClient
from fastapi import HTTPException
from sqlalchemy.orm import Session
from . import models, schemas


# --- Stock CRUD ---

def get_stocks(db: Session):
    return db.query(models.Stock).all()

def create_stock(db: Session, stock: schemas.StockCreate):
    db_stock = models.Stock(
        ticker=stock.ticker,
        shares=stock.shares,
        cost_basis=stock.cost_basis,
        market_price=stock.market_price,
        status=stock.status,
        entry_date=str(stock.entry_date) if stock.entry_date else None
    )
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock

def update_stock(db: Session, stock_id: int, stock_data: schemas.StockCreate):
    db_stock = db.query(models.Stock).filter(models.Stock.id == stock_id).first()
    if db_stock:
        db_stock.ticker = stock_data.ticker
        db_stock.shares = stock_data.shares
        db_stock.cost_basis = stock_data.cost_basis
        db_stock.market_price = stock_data.market_price
        db_stock.status = stock_data.status
        db_stock.entry_date = str(stock_data.entry_date) if stock_data.entry_date else None
        db.commit()
        db.refresh(db_stock)
    return db_stock

def delete_stock(db: Session, id: int):
    stock = db.query(models.Stock).filter(models.Stock.id == id).first()
    if stock:
        db.delete(stock)
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
