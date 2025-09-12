# Simple models stub to fix immediate import issues
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Date, Text
from sqlalchemy.orm import relationship
from datetime import datetime, date, UTC

# Import the Base from the database module
try:
    from .database import Base
except ImportError:
    # Fallback for testing
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

# Essential models needed for the app to start
class Stock(Base):
    __tablename__ = "stocks"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    shares = Column(Float)
    cost_basis = Column(Float)
    market_price = Column(Float, nullable=True)
    status = Column(String, default="Open")

class Ticker(Base):
    __tablename__ = "tickers"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    last_price = Column(String, nullable=True)
    change = Column(String, nullable=True)
    change_percent = Column(String, nullable=True)
    volume = Column(String, nullable=True)
    market_cap = Column(String, nullable=True)
    timestamp = Column(String, nullable=True)

class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True, index=True)
    ticker_id = Column(Integer, ForeignKey("tickers.id"))
    price = Column(Float)
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    roles = Column(String, default="")
    
    # Schwab OAuth tokens
    schwab_access_token = Column(String, nullable=True)
    schwab_refresh_token = Column(String, nullable=True)
    schwab_token_expires_at = Column(DateTime, nullable=True)
    schwab_account_linked = Column(Boolean, default=False)

# Additional models for compatibility
class Option(Base):
    __tablename__ = "options"
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String)

class WheelStrategy(Base):
    __tablename__ = "wheel_strategies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

class WheelCycle(Base):
    __tablename__ = "wheel_cycles"
    id = Column(Integer, primary_key=True, index=True)
    cycle_key = Column(String, unique=True, index=True)
    ticker = Column(String, index=True)
    started_at = Column(Date, nullable=True)
    status = Column(String, default="Open")
    notes = Column(Text, nullable=True)
    strategy_type = Column(String, nullable=True)
    detection_metadata = Column(Text, nullable=True)  # JSON stored as text
    status_metadata = Column(Text, nullable=True)  # JSON stored as text for transition context
    last_status_update = Column(DateTime, default=lambda: datetime.now(UTC))
    
    # Real-time P&L fields
    current_option_value = Column(Float, nullable=True)  # Current market value of option positions
    unrealized_pnl = Column(Float, nullable=True)  # Premium collected - current option value
    total_pnl = Column(Float, nullable=True)  # Total realized + unrealized P&L
    price_last_updated = Column(DateTime, nullable=True)  # Timestamp of last price refresh

class WheelStatusHistory(Base):
    __tablename__ = "wheel_status_history"
    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("wheel_cycles.id"), index=True)
    previous_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    trigger_event = Column(String, nullable=False)  # 'manual', 'assignment', 'expiration', 'position_change'
    automated = Column(Boolean, default=False)
    event_metadata = Column(Text, nullable=True)  # JSON stored as text (renamed from 'metadata' to avoid SQLAlchemy conflict)
    updated_by = Column(String, nullable=True)  # User who made the change
    timestamp = Column(DateTime, default=lambda: datetime.now(UTC))
    
    # Relationship to wheel cycle
    cycle = relationship("WheelCycle", backref="status_history")

class WheelEvent(Base):
    __tablename__ = "wheel_events"
    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("wheel_cycles.id"), index=True)
    event_type = Column(String, nullable=False)  # e.g., "SELL_PUT_OPEN", "SELL_PUT_CLOSE", etc.
    event_date = Column(Date, nullable=True)
    contracts = Column(Float, nullable=True)  # Number of contracts
    strike = Column(Float, nullable=True)     # Strike price
    premium = Column(Float, nullable=True)    # Premium received/paid
    notes = Column(Text, nullable=True)
    name = Column(String, nullable=True)      # Keep for backward compatibility
    
    # Relationship to wheel cycle
    cycle = relationship("WheelCycle", backref="events")

class Lot(Base):
    __tablename__ = "lots"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

class LotLink(Base):
    __tablename__ = "lot_links"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

class LotMetrics(Base):
    __tablename__ = "lot_metrics"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

# Models expected by imports
class Wheel(Base):
    __tablename__ = "wheels"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

class WheelEventImport(Base):
    __tablename__ = "wheel_event_imports"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)

class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

class Test(Base):
    __tablename__ = "tests"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

class SpreadOption(Base):
    __tablename__ = "spread_options"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)

# Schwab models for new functionality
class SchwabAccount(Base):
    __tablename__ = "schwab_accounts"
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String, unique=True, index=True, nullable=False)
    hash_value = Column(String, nullable=False)
    account_type = Column(String)
    is_day_trader = Column(Boolean, default=False)
    last_synced = Column(DateTime, default=lambda: datetime.now(UTC))
    cash_balance = Column(Float, default=0.0)
    buying_power = Column(Float, default=0.0)
    total_value = Column(Float, default=0.0)
    day_trading_buying_power = Column(Float, default=0.0)

class SchwabPosition(Base):
    __tablename__ = "schwab_positions"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("schwab_accounts.id"), nullable=False)
    symbol = Column(String, index=True, nullable=False)
    instrument_cusip = Column(String)
    asset_type = Column(String)
    underlying_symbol = Column(String, index=True)
    option_type = Column(String)
    strike_price = Column(Float)
    expiration_date = Column(DateTime)
    long_quantity = Column(Float, default=0.0)
    short_quantity = Column(Float, default=0.0)
    settled_long_quantity = Column(Float, default=0.0)
    settled_short_quantity = Column(Float, default=0.0)
    market_value = Column(Float, default=0.0)
    average_price = Column(Float, default=0.0)
    average_long_price = Column(Float, default=0.0)
    average_short_price = Column(Float, default=0.0)
    current_day_profit_loss = Column(Float, default=0.0)
    current_day_profit_loss_percentage = Column(Float, default=0.0)
    long_open_profit_loss = Column(Float, default=0.0)
    short_open_profit_loss = Column(Float, default=0.0)
    last_updated = Column(DateTime, default=lambda: datetime.now(UTC))
    is_active = Column(Boolean, default=True)
    raw_data = Column(String)

class PositionSnapshot(Base):
    __tablename__ = "position_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("schwab_accounts.id"), nullable=False)
    snapshot_date = Column(DateTime, default=lambda: datetime.now(UTC))
    total_positions = Column(Integer, default=0)
    total_value = Column(Float, default=0.0)
    total_profit_loss = Column(Float, default=0.0)
    stock_count = Column(Integer, default=0)
    option_count = Column(Integer, default=0)
    stock_value = Column(Float, default=0.0)
    option_value = Column(Float, default=0.0)
