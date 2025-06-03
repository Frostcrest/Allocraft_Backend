from sqlalchemy import Column, Integer, String, Float
from .database import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    shares = Column(Float)
    cost_basis = Column(Float)
    market_price = Column(Float, nullable=True)
    status = Column(String, default="Open")  # "Open" or "Sold"
    entry_date = Column(String)  # Use Date if you want more type safety


class Ticker(Base):
    """SQLAlchemy model for a market ticker."""
    __tablename__ = "tickers"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    name = Column(String, nullable=True)
    last_price = Column(String, nullable=True)
    change = Column(String, nullable=True)
    change_percent = Column(String, nullable=True)
    volume = Column(String, nullable=True)
    market_cap = Column(String, nullable=True)
    timestamp = Column(String, nullable=True)  # Use appropriate type for timestamp if needed


class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    option_type = Column(String)  # "Call" or "Put"
    strike_price = Column(Float)
    expiry_date = Column(String)  # Use Date if you want more type safety
    contracts = Column(Float)
    cost = Column(Float)
    market_price_per_contract = Column(Float, nullable=True)
    status = Column(String, default="Open")  # "Open" or "Closed"


class LEAP(Base):
    __tablename__ = "leaps"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    contract_info = Column(String)  # e.g., "$150 Call Jan 2026"
    cost = Column(Float)
    current_price = Column(Float, nullable=True)
    expiry_date = Column(String)  # Use Date if you want more type safety


class WheelStrategy(Base):
    __tablename__ = "wheel_strategies"

    id = Column(Integer, primary_key=True, index=True)
    wheel_id = Column(String, index=True)
    ticker = Column(String, index=True)
    trade_type = Column(String)  # "Sell Put", "Assignment", "Sell Call", "Called Away"
    trade_date = Column(String)  # Use Date if you want more type safety
    strike_price = Column(Float, nullable=True)
    premium_received = Column(Float, nullable=True)
    status = Column(String, default="Active")  # "Active" or "Closed"
