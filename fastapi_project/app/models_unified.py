"""
Unified Data Models - Source Agnostic Portfolio Management

This replaces both legacy and Schwab-specific models with a unified,
objectively better data structure that handles any brokerage source.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from datetime import datetime
from .database import Base

class Account(Base):
    """
    Unified account model - handles any brokerage account
    """
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String, unique=True, index=True, nullable=False)
    account_type = Column(String)  # MARGIN, CASH, etc.
    brokerage = Column(String, default="manual")  # schwab, fidelity, manual, etc.
    hash_value = Column(String, nullable=True)  # For external account linking
    is_day_trader = Column(Boolean, default=False)
    
    # Financial data
    cash_balance = Column(Float, default=0.0)
    buying_power = Column(Float, default=0.0)
    total_value = Column(Float, default=0.0)
    day_trading_buying_power = Column(Float, default=0.0)
    
    # Metadata
    last_synced = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Position(Base):
    """
    Unified position model - handles stocks, options, ETFs, etc.
    Replaces both legacy Stock/Option models and SchwabPosition
    """
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    
    # Symbol and identification
    symbol = Column(String, index=True, nullable=False)  # Full symbol (e.g., "AAPL", "AAPL 240315C00180000")
    underlying_symbol = Column(String, index=True)  # For options: "AAPL", for stocks: same as symbol
    asset_type = Column(String, nullable=False)  # EQUITY, OPTION, COLLECTIVE_INVESTMENT, etc.
    instrument_cusip = Column(String)
    
    # Option-specific fields (null for non-options)
    option_type = Column(String)  # CALL, PUT
    strike_price = Column(Float)
    expiration_date = Column(DateTime)
    
    # Quantities (unified approach handles long/short)
    long_quantity = Column(Float, default=0.0)
    short_quantity = Column(Float, default=0.0)
    settled_long_quantity = Column(Float, default=0.0)
    settled_short_quantity = Column(Float, default=0.0)
    
    # Pricing and value
    market_value = Column(Float, default=0.0)
    average_price = Column(Float, default=0.0)  # Cost basis per share/contract
    average_long_price = Column(Float, default=0.0)
    average_short_price = Column(Float, default=0.0)
    current_price = Column(Float, nullable=True)  # Latest market price
    
    # P&L tracking
    current_day_profit_loss = Column(Float, default=0.0)
    current_day_profit_loss_percentage = Column(Float, default=0.0)
    long_open_profit_loss = Column(Float, default=0.0)
    short_open_profit_loss = Column(Float, default=0.0)
    
    # Legacy compatibility fields (valuable manual entry data)
    entry_date = Column(String)  # User-specified entry date
    status = Column(String, default="Open")  # Open, Closed, Sold
    
    # Metadata
    last_updated = Column(DateTime, default=datetime.utcnow)
    price_last_updated = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    raw_data = Column(String)  # Store original API response for debugging
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Source tracking (for data lineage)
    data_source = Column(String, default="manual")  # manual, schwab, fidelity, etc.


class PortfolioSnapshot(Base):
    """
    Point-in-time portfolio snapshots for performance tracking
    """
    __tablename__ = "portfolio_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    snapshot_date = Column(DateTime, default=datetime.utcnow)
    
    # Aggregate metrics
    total_positions = Column(Integer, default=0)
    total_value = Column(Float, default=0.0)
    total_profit_loss = Column(Float, default=0.0)
    
    # Asset type breakdowns
    stock_count = Column(Integer, default=0)
    option_count = Column(Integer, default=0)
    stock_value = Column(Float, default=0.0)
    option_value = Column(Float, default=0.0)


# Note: Existing models (Ticker, Price, User) will be imported from original models.py
# to avoid table definition conflicts during migration phase


# Note: Wheel strategy models will be imported from original models.py
# to avoid table definition conflicts during migration phase
