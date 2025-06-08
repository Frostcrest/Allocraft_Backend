from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
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
    symbol = Column(String, index=True)                 # Ticker symbol (e.g., "AAPL")
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
    trade_type = Column(String)
    trade_date = Column(String)
    strike_price = Column(Float, nullable=True)
    premium_received = Column(Float, nullable=True)
    status = Column(String, default="Active")
    call_put = Column(String, nullable=True)

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

class Price(Base):
    """
    Represents a historical or latest price for a ticker.
    """
    __tablename__ = "prices"

    id = Column(Integer, primary_key=True, index=True)      # Unique ID for each price row
    price = Column(Float, nullable=False)                   # Price value
    ticker_id = Column(Integer, ForeignKey("tickers.id"), nullable=False) # Associated ticker ID
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False) # When the price was recorded

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
