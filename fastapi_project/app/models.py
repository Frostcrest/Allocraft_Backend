from sqlalchemy import Column, Integer, String, Float
from .database import Base


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    quantity = Column(Integer)
    average_price = Column(Float, nullable=True)  # Optional field for average price

    
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
