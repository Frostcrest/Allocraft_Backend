from pydantic import BaseModel, Field
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
    wheel_id: str = Field(..., description="Unique identifier for wheel strategy (e.g., 'AAPL-W1')")
    ticker: str = Field(..., description="Stock ticker for wheel strategy")
    trade_type: Literal["Sell Put", "Assignment", "Sell Call", "Called Away"] = Field(..., description="Type of wheel trade")
    trade_date: date = Field(..., description="Date of the trade")
    strike_price: Optional[float] = Field(None, description="Strike price if applicable")
    premium_received: Optional[float] = Field(None, description="Premium received from trade")
    status: Literal["Open", "Active", "Closed"] = Field("Open", description="Trade status")  # Accepts "Open", "Active", or "Closed"
    call_put: Optional[str] = Field(None, description="Call or Put")  # Optional, for clarity

class WheelStrategyCreate(WheelStrategyBase):
    """Schema for creating a new wheel strategy trade."""
    pass

class WheelStrategyRead(WheelStrategyBase):
    """Schema for reading a wheel strategy trade from the database."""
    id: int

    class Config:
        orm_mode = True