from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Index, UniqueConstraint
from datetime import datetime
from .database import Base

# --- SQLAlchemy ORM Models ---
# These classes define the structure of your database tables.
# Each class represents a table, and each attribute represents a column.

class Stock(Base):
    """
    Represents a stock position in the user's portfolio.
    """
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)  # Unique ID for each stock row
    ticker = Column(String, index=True)                 # Stock symbol (e.g., "AAPL")
    shares = Column(Float)                              # Number of shares owned
    cost_basis = Column(Float)                          # Average cost per share
    market_price = Column(Float, nullable=True)         # Market price at time of entry (optional)
    status = Column(String, default="Open")             # "Open" or "Sold"
    entry_date = Column(String)                         # Date the position was opened (as string)
    current_price = Column(Float, nullable=True)        # Latest fetched price (updates with refresh)
    price_last_updated = Column(DateTime, nullable=True) # When the price was last updated

class Ticker(Base):
    """
    Represents a market ticker (symbol) and its latest quote data.
    Used for reference and price lookups.
    """
    __tablename__ = "tickers"

    id = Column(Integer, primary_key=True, index=True)  # Unique ID for each ticker
    symbol = Column(String, unique=True, index=True)    # Ticker symbol (e.g., "AAPL"), unique for integrity
    name = Column(String, nullable=True)                # Company name (optional)
    last_price = Column(String, nullable=True)          # Last known price (as string)
    change = Column(String, nullable=True)              # Price change (as string)
    change_percent = Column(String, nullable=True)      # Percent change (as string)
    volume = Column(String, nullable=True)              # Trading volume (as string)
    market_cap = Column(String, nullable=True)          # Market capitalization (as string)
    timestamp = Column(String, nullable=True)           # Last update time (as string)

class Option(Base):
    """
    Represents an options contract in the user's portfolio.
    """
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)      # Unique ID for each option row
    ticker = Column(String, index=True)                     # Underlying stock symbol
    option_type = Column(String)                            # "Call" or "Put"
    strike_price = Column(Float)                            # Strike price of the option
    expiry_date = Column(String)                            # Expiry date (as "YYYY-MM-DD" string)
    contracts = Column(Float)                               # Number of contracts
    cost_basis = Column(Float)                              # Cost per contract (not total)
    market_price_per_contract = Column(Float, nullable=True) # Latest fetched price per contract
    status = Column(String, default="Open")                 # "Open" or "Closed"
    current_price = Column(Float, nullable=True)            # Latest fetched price (for UI/refresh)

class WheelStrategy(Base):
    """
    Represents a wheel options trading strategy step.
    Each row is a single trade in the wheel process.
    """
    __tablename__ = "wheel_strategies"

    id = Column(Integer, primary_key=True, index=True)
    wheel_id = Column(String, index=True)
    ticker = Column(String, index=True)
    trade_date = Column(String)

    # New fields for full wheel lifecycle
    sell_put_strike_price = Column(Float, nullable=True)
    sell_put_open_premium = Column(Float, nullable=True)
    sell_put_closed_premium = Column(Float, nullable=True)
    sell_put_status = Column(String, nullable=True)
    sell_put_quantity = Column(Integer, nullable=True)

    assignment_strike_price = Column(Float, nullable=True)
    assignment_shares_quantity = Column(Integer, nullable=True)
    assignment_status = Column(String, nullable=True)

    sell_call_strike_price = Column(Float, nullable=True)
    sell_call_open_premium = Column(Float, nullable=True)
    sell_call_closed_premium = Column(Float, nullable=True)
    sell_call_status = Column(String, nullable=True)
    sell_call_quantity = Column(Integer, nullable=True)

    called_away_strike_price = Column(Float, nullable=True)
    called_away_shares_quantity = Column(Integer, nullable=True)
    called_away_status = Column(String, nullable=True)


class WheelCycle(Base):
    """
    Event-based Wheel cycle container. Tracks a single wheel run for a ticker.
    """
    __tablename__ = "wheel_cycles"

    id = Column(Integer, primary_key=True, index=True)
    cycle_key = Column(String, unique=True, index=True)  # e.g., "AAPL-1" must be unique
    ticker = Column(String, index=True)
    started_at = Column(String, nullable=True)  # ISO date string
    status = Column(String, default="Open")  # Open/Closed
    notes = Column(String, nullable=True)


class WheelEvent(Base):
    """
    A single event within a WheelCycle. Enables adding entries at any stage
    (buy shares, sell calls/puts, assignment, called away, sell shares, etc.)
    and linking related open/close pairs via link_event_id.
    """
    __tablename__ = "wheel_events"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("wheel_cycles.id"), index=True, nullable=False)
    event_type = Column(String, index=True)  # Enum-like string
    trade_date = Column(String, nullable=True)  # ISO date string

    # Common numerical fields (optional depending on event_type)
    quantity_shares = Column(Float, nullable=True)
    contracts = Column(Integer, nullable=True)
    price = Column(Float, nullable=True)    # share price for buy/sell, or general amount
    strike = Column(Float, nullable=True)   # strike associated with options/assignment
    premium = Column(Float, nullable=True)  # premium per contract
    fees = Column(Float, nullable=True)     # commissions/fees (positive = cost)

    # Link to another event (e.g., CLOSE referencing OPEN; called away referencing sold call)
    link_event_id = Column(Integer, ForeignKey("wheel_events.id"), nullable=True)
    notes = Column(String, nullable=True)

    # Composite index to accelerate common queries/sorts
    __table_args__ = (
        Index("ix_wheel_events_cycle_date_id", "cycle_id", "trade_date", "id"),
    )


class Lot(Base):
    """Represents a 100-share lot within a wheel cycle."""
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True, index=True)
    cycle_id = Column(Integer, ForeignKey("wheel_cycles.id"), index=True, nullable=False)
    ticker = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    acquisition_method = Column(String, index=True)  # PUT_ASSIGNMENT, OUTRIGHT_PURCHASE, CORPORATE_ACTION
    acquisition_date = Column(String, nullable=True)
    status = Column(String, index=True, default="OPEN_UNCOVERED")
    cost_basis_effective = Column(Float, nullable=True)
    notes = Column(String, nullable=True)

    __table_args__ = (
        Index("ix_lots_cycle_status", "cycle_id", "status"),
    )


class LotLink(Base):
    """Links a lot to source events/trades to preserve audit trail."""
    __tablename__ = "lot_links"

    id = Column(Integer, primary_key=True, index=True)
    lot_id = Column(Integer, ForeignKey("lots.id"), index=True, nullable=False)
    linked_object_type = Column(String, index=True)  # e.g., WHEEL_EVENT
    linked_object_id = Column(Integer, index=True)
    role = Column(String, index=True)  # PUT_SOLD, PUT_ASSIGNMENT, STOCK_BUY, CALL_OPEN, CALL_CLOSE, CALL_ASSIGNMENT, STOCK_SELL, FEE, ADJUSTMENT

    __table_args__ = (
        Index("ix_lot_links_lot_role", "lot_id", "role"),
    )


class LotMetrics(Base):
    """Materialized metrics for a lot for fast reads."""
    __tablename__ = "lot_metrics"

    lot_id = Column(Integer, ForeignKey("lots.id"), primary_key=True, index=True)
    net_premiums = Column(Float, default=0.0)
    stock_cost_total = Column(Float, default=0.0)
    fees_total = Column(Float, default=0.0)
    realized_pl = Column(Float, default=0.0)
    unrealized_pl = Column(Float, default=0.0)

class Price(Base):
    """
    Represents a historical or latest price for a ticker.
    """
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, index=True)      # Unique ID for each price row
    price = Column(Float, nullable=False)                   # Price value
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False) # Associated ticker ID
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False) # When the price was recorded

    __table_args__ = (
        Index("ix_prices_ticker_time", "ticker_id", "timestamp"),
    )

class User(Base):
    """
    Represents an application user with authentication and role-based access.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    roles = Column(String, default="user")  # Comma-separated roles, e.g., "user,admin"
    
    # Schwab OAuth tokens
    schwab_access_token = Column(String, nullable=True)
    schwab_refresh_token = Column(String, nullable=True)
    schwab_token_expires_at = Column(DateTime, nullable=True)
