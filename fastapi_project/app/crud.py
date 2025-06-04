from app.services.price_service import (
    fetch_latest_price,
    fetch_yf_price,
    fetch_option_contract_price,
)
from fastapi import HTTPException
from sqlalchemy.orm import Session
from . import models, schemas
from datetime import datetime
import requests
import yfinance as yf
from twelvedata import TDClient

# --- Stock CRUD Operations ---

def get_stocks(db: Session, refresh_prices: bool = False):
    """
    Get all stocks from the database.
    If refresh_prices is True, update their current prices before returning.
    """
    stocks = db.query(models.Stock).all()
    if refresh_prices:
        for stock in stocks:
            price, updated = fetch_latest_price(stock.ticker)
            stock.current_price = price
            stock.price_last_updated = updated
        db.commit()
    return stocks

def create_stock(db: Session, stock: schemas.StockCreate):
    """
    Create a new stock entry in the database.
    Fetches the latest price and stores it as current_price.
    """
    price, updated = fetch_latest_price(stock.ticker)
    db_stock = models.Stock(
        ticker=stock.ticker,
        shares=stock.shares,
        cost_basis=stock.cost_basis,
        market_price=stock.market_price,
        status=stock.status,
        entry_date=str(stock.entry_date) if stock.entry_date else None,
        current_price=price,
        price_last_updated=updated,
    )
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock

def update_stock(db: Session, stock_id: int, stock_data: schemas.StockCreate):
    """
    Update an existing stock entry by ID.
    Also refreshes the current price.
    """
    db_stock = db.query(models.Stock).filter(models.Stock.id == stock_id).first()
    if db_stock:
        db_stock.ticker = stock_data.ticker
        db_stock.shares = stock_data.shares
        db_stock.cost_basis = stock_data.cost_basis
        db_stock.market_price = stock_data.market_price
        db_stock.status = stock_data.status
        db_stock.entry_date = str(stock_data.entry_date) if stock_data.entry_date else None
        # Optionally refresh price on update
        price, updated = fetch_latest_price(stock_data.ticker)
        db_stock.current_price = price
        db_stock.price_last_updated = updated
        db.commit()
        db.refresh(db_stock)
    return db_stock

def delete_stock(db: Session, id: int):
    """
    Delete a stock entry by ID.
    Returns True if deleted, False if not found.
    """
    stock = db.query(models.Stock).filter(models.Stock.id == id).first()
    if stock:
        db.delete(stock)
        db.commit()
        return True
    return False

# --- Option CRUD Operations ---

def get_options(db: Session):
    """
    Get all options from the database.
    """
    return db.query(models.Option).all()

def create_option(db: Session, option: schemas.OptionCreate):
    """
    Create a new option entry in the database.
    Fetches the latest price for the option contract.
    """
    option_price = fetch_option_contract_price(
        option.ticker,
        str(option.expiry_date),
        option.option_type,
        option.strike_price
    )
    db_option = models.Option(
        ticker=option.ticker,
        option_type=option.option_type,
        strike_price=option.strike_price,
        expiry_date=str(option.expiry_date),
        contracts=option.contracts,
        cost_basis=option.cost_basis,  # Cost per contract
        market_price_per_contract=option_price,
        status=option.status,
        current_price=option_price,
    )
    db.add(db_option)
    db.commit()
    db.refresh(db_option)
    return db_option

def update_option(db: Session, option_id: int, option_data: schemas.OptionCreate):
    """
    Update an existing option entry by ID.
    Also refreshes the option's current price.
    """
    db_option = db.query(models.Option).filter(models.Option.id == option_id).first()
    if db_option:
        db_option.ticker = option_data.ticker
        db_option.option_type = option_data.option_type
        db_option.strike_price = option_data.strike_price
        db_option.expiry_date = str(option_data.expiry_date)
        db_option.contracts = option_data.contracts
        db_option.cost_basis = option_data.cost_basis
        option_price = fetch_option_contract_price(
            option_data.ticker,
            str(option_data.expiry_date),
            option_data.option_type,
            option_data.strike_price
        )
        db_option.market_price_per_contract = option_price
        db_option.current_price = option_price
        db_option.status = option_data.status
        db.commit()
        db.refresh(db_option)
    return db_option

def delete_option(db: Session, id: int):
    """
    Delete an option entry by ID.
    Returns True if deleted, False if not found.
    """
    option = db.query(models.Option).filter(models.Option.id == id).first()
    if option:
        db.delete(option)
        db.commit()
        return True
    return False

# --- Ticker CRUD Operations ---

TD_API_KEY = "59076e2930e5489796d3f74ea7082959"
td = TDClient(apikey=TD_API_KEY)

def fetch_ticker_info(symbol: str) -> dict:
    """
    Fetch ticker info from Twelve Data API.
    Returns a dictionary with symbol, name, last price, etc.
    Raises HTTPException if not found or API fails.
    """
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
    """
    Create and persist a new ticker by symbol.
    If it already exists, returns the existing ticker.
    """
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
    """
    Get a ticker by its symbol.
    Returns the ticker object or None if not found.
    """
    return db.query(models.Ticker).filter(models.Ticker.symbol == symbol).first()

def get_ticker_by_id(db: Session, ticker_id: int):
    """
    Get a ticker by its ID.
    Raises HTTPException if not found.
    """
    ticker = db.query(models.Ticker).filter(models.Ticker.id == ticker_id).first()
    if not ticker:
        raise HTTPException(status_code=404, detail="Ticker not found.")
    return ticker

def get_tickers(db: Session):
    """
    Return all tickers in the database.
    """
    return db.query(models.Ticker).all()

def delete_ticker(db: Session, ticker_id: int):
    """
    Delete a ticker by ID.
    Raises HTTPException if not found.
    """
    ticker = db.query(models.Ticker).filter(models.Ticker.id == ticker_id).first()
    if ticker:
        db.delete(ticker)
        db.commit()
        return True
    raise HTTPException(status_code=404, detail="Ticker not found.")

# --- WheelStrategy CRUD Operations ---

def get_wheels(db: Session):
    """
    Get all wheel strategies from the database.
    """
    return db.query(models.WheelStrategy).all()

def create_wheel(db: Session, wheel: schemas.WheelStrategyCreate):
    """
    Create a new wheel strategy entry in the database.
    """
    db_wheel = models.WheelStrategy(
        wheel_id=wheel.wheel_id,
        ticker=wheel.ticker,
        trade_type=wheel.trade_type,
        trade_date=str(wheel.trade_date),
        strike_price=wheel.strike_price,
        premium_received=wheel.premium_received,
        status=wheel.status,
    )
    db.add(db_wheel)
    db.commit()
    db.refresh(db_wheel)
    return db_wheel

def update_wheel(db: Session, wheel_id: int, wheel_data: schemas.WheelStrategyCreate):
    """
    Update an existing wheel strategy entry by ID.
    """
    db_wheel = db.query(models.WheelStrategy).filter(models.WheelStrategy.id == wheel_id).first()
    if db_wheel:
        db_wheel.wheel_id = wheel_data.wheel_id
        db_wheel.ticker = wheel_data.ticker
        db_wheel.trade_type = wheel_data.trade_type
        db_wheel.trade_date = str(wheel_data.trade_date)
        db_wheel.strike_price = wheel_data.strike_price
        db_wheel.premium_received = wheel_data.premium_received
        db_wheel.status = wheel_data.status
        db.commit()
        db.refresh(db_wheel)
    return db_wheel

def delete_wheel(db: Session, id: int):
    """
    Delete a wheel strategy entry by ID.
    Returns True if deleted, False if not found.
    """
    wheel = db.query(models.WheelStrategy).filter(models.WheelStrategy.id == id).first()
    if wheel:
        db.delete(wheel)
        db.commit()
        return True
    return False
