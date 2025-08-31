from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from ..database import Base

class SchwabAccount(Base):
    __tablename__ = "schwab_accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String, unique=True, index=True, nullable=False)
    hash_value = Column(String, nullable=False)
    account_type = Column(String)  # MARGIN, CASH, etc.
    is_day_trader = Column(Boolean, default=False)
    last_synced = Column(DateTime, default=datetime.utcnow)
    
    # Account balances
    cash_balance = Column(Float, default=0.0)
    buying_power = Column(Float, default=0.0)
    total_value = Column(Float, default=0.0)
    day_trading_buying_power = Column(Float, default=0.0)
    
    # Relationships
    positions = relationship("SchwabPosition", back_populates="account", cascade="all, delete-orphan")
    
class SchwabPosition(Base):
    __tablename__ = "schwab_positions"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("schwab_accounts.id"), nullable=False)
    
    # Position identification
    symbol = Column(String, index=True, nullable=False)
    instrument_cusip = Column(String)
    asset_type = Column(String)  # EQUITY, OPTION, etc.
    
    # For options
    underlying_symbol = Column(String, index=True)
    option_type = Column(String)  # CALL, PUT
    strike_price = Column(Float)
    expiration_date = Column(DateTime)
    
    # Position quantities
    long_quantity = Column(Float, default=0.0)
    short_quantity = Column(Float, default=0.0)
    settled_long_quantity = Column(Float, default=0.0)
    settled_short_quantity = Column(Float, default=0.0)
    
    # Pricing information
    market_value = Column(Float, default=0.0)
    average_price = Column(Float, default=0.0)
    average_long_price = Column(Float, default=0.0)
    average_short_price = Column(Float, default=0.0)
    
    # P&L information
    current_day_profit_loss = Column(Float, default=0.0)
    current_day_profit_loss_percentage = Column(Float, default=0.0)
    long_open_profit_loss = Column(Float, default=0.0)
    short_open_profit_loss = Column(Float, default=0.0)
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Raw data for reference
    raw_data = Column(Text)  # JSON string of original Schwab response
    
    # Relationships
    account = relationship("SchwabAccount", back_populates="positions")

class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("schwab_accounts.id"), nullable=False)
    snapshot_date = Column(DateTime, default=datetime.utcnow)
    total_positions = Column(Integer, default=0)
    total_value = Column(Float, default=0.0)
    total_profit_loss = Column(Float, default=0.0)
    
    # Breakdown by asset type
    stock_count = Column(Integer, default=0)
    option_count = Column(Integer, default=0)
    stock_value = Column(Float, default=0.0)
    option_value = Column(Float, default=0.0)