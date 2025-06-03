from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    position_type = Column(String)  # e.g., 'stock', 'call', 'put'
    quantity = Column(Float)
    average_price = Column(Float)
    expiry = Column(String, nullable=True)  # only for options
    strike_price = Column(Float, nullable=True)  # only for options
    side = Column(String, nullable=True)  # e.g., 'long', 'short'

    # Optional: link to ticker or user
    # ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=True)


class Ticker(Base):
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
