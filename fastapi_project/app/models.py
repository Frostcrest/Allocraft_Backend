from sqlalchemy import Column, Integer, String
from app.database import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)

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
