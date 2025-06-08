from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import date, datetime

# --- STOCK SCHEMAS ---
# These classes define the structure of data for stocks.
# They are used for request validation and response formatting.

class StockBase(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    shares: float = Field(..., description="Number of shares owned")
    cost_basis: float = Field(..., description="Cost per share")
    market_price: Optional[float] = Field(None, description="Current market price per share")
    status: Literal["Open", "Sold"] = Field("Open", description="Position status")
    entry_date: Optional[date] = Field(None, description="Date position was opened")
    current_price: Optional[float] = Field(None, description="Latest fetched price")
    price_last_updated: Optional[datetime] = Field(None, description="Timestamp of last price update")

class StockCreate(StockBase):
    """Schema for creating a new stock position."""
    pass

class StockRead(StockBase):
    """Schema for reading a stock position from the database."""
    id: int

    class Config:
        orm_mode = True  # Allows reading from ORM objects directly

# --- TICKER SCHEMAS ---
# These classes define the structure of data for ticker symbols (market data lookups).

class TickerBase(BaseModel):
    """Base schema for a market ticker."""
    symbol: str
    name: Optional[str] = None
    last_price: Optional[str] = None
    change: Optional[str] = None
    change_percent: Optional[str] = None
    volume: Optional[str] = None
    market_cap: Optional[str] = None
    timestamp: Optional[str] = None  # You can use datetime if desired

class TickerCreate(BaseModel):
    """Schema for creating a ticker."""
    symbol: str
    
class TickerRead(TickerBase):
    """Schema for reading a ticker from the database."""
    id: int

    class Config:
        orm_mode = True

# --- OPTION SCHEMAS ---
# These classes define the structure of data for options contracts.

class OptionBase(BaseModel):
    ticker: str = Field(..., description="Underlying stock ticker")
    option_type: Literal["Call", "Put"] = Field(..., description="Type of option contract")
    strike_price: float = Field(..., description="Strike price of the option")
    expiry_date: date = Field(..., description="Option expiration date")
    contracts: float = Field(..., description="Number of contracts")
    cost_basis: float = Field(..., description="Cost basis per contract")  # Cost per contract, not total
    market_price_per_contract: Optional[float] = Field(None, description="Current market price per contract")
    status: Literal["Open", "Closed"] = Field("Open", description="Contract status")
    current_price: Optional[float] = Field(None, description="Current price of the underlying")

class OptionCreate(OptionBase):
    """Schema for creating a new option contract."""
    pass

class OptionRead(OptionBase):
    """Schema for reading an option contract from the database."""
    id: int

    class Config:
        orm_mode = True

# --- WHEEL STRATEGY SCHEMAS ---
# These classes define the structure of data for wheel strategy trades.

class WheelStrategyBase(BaseModel):
    wheel_id: str
    ticker: str
    trade_date: date

    # New fields for full wheel lifecycle
    sell_put_strike_price: Optional[float] = None
    sell_put_open_premium: Optional[float] = None
    sell_put_closed_premium: Optional[float] = None
    sell_put_status: Optional[str] = None
    sell_put_quantity: Optional[int] = None

    assignment_strike_price: Optional[float] = None
    assignment_shares_quantity: Optional[int] = None
    assignment_status: Optional[str] = None

    sell_call_strike_price: Optional[float] = None
    sell_call_open_premium: Optional[float] = None
    sell_call_closed_premium: Optional[float] = None
    sell_call_status: Optional[str] = None
    sell_call_quantity: Optional[int] = None

    called_away_strike_price: Optional[float] = None
    called_away_shares_quantity: Optional[int] = None
    called_away_status: Optional[str] = None

class WheelStrategyCreate(WheelStrategyBase):
    """Schema for creating a new wheel strategy trade."""
    pass

class WheelStrategyRead(WheelStrategyBase):
    """Schema for reading a wheel strategy trade from the database."""
    id: int

    class Config:
        orm_mode = True

# --- USER SCHEMAS ---

class UserBase(BaseModel):
    username: str = Field(..., description="Unique username")
    email: EmailStr = Field(..., description="User email address")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="User password")

class UserRead(UserBase):
    id: int
    is_active: bool
    roles: str

    class Config:
        orm_mode = True

class UserLogin(BaseModel):
    username: str
    password: str

# --- JWT Token SCHEMAS ---

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    roles: Optional[str] = None