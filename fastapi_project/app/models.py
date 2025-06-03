from sqlalchemy import Column, Integer, String, Float, Date
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

    
class OptionPosition(Base):
    __tablename__ = "option_positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    option_type = Column(String)  # 'call' or 'put'
    strike_price = Column(Float)
    expiration_date = Column(String)  # use Date if you want more type safety
    quantity = Column(Integer)


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
