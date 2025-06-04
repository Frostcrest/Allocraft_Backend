from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date, datetime


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
    pass

class StockRead(StockBase):
    id: int

    class Config:
        orm_mode = True


# This file defines the Pydantic schemas for the Ticker model.
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

class OptionBase(BaseModel):
    ticker: str = Field(..., description="Underlying stock ticker")
    option_type: Literal["Call", "Put"] = Field(..., description="Type of option contract")
    strike_price: float = Field(..., description="Strike price of the option")
    expiry_date: date = Field(..., description="Option expiration date")
    contracts: float = Field(..., description="Number of contracts")
    cost_basis: float = Field(..., description="Cost basis per contract")  # <-- Renamed
    market_price_per_contract: Optional[float] = Field(None, description="Current market price per contract")
    status: Literal["Open", "Closed"] = Field("Open", description="Contract status")
    current_price: Optional[float] = Field(None, description="Current price of the underlying")

class OptionCreate(OptionBase):
    pass

class OptionRead(OptionBase):
    id: int

    class Config:
        orm_mode = True

class WheelStrategyBase(BaseModel):
    wheel_id: str = Field(..., description="Unique identifier for wheel strategy (e.g., 'AAPL-W1')")
    ticker: str = Field(..., description="Stock ticker for wheel strategy")
    trade_type: Literal["Sell Put", "Assignment", "Sell Call", "Called Away"] = Field(..., description="Type of wheel trade")
    trade_date: date = Field(..., description="Date of the trade")
    strike_price: Optional[float] = Field(None, description="Strike price if applicable")
    premium_received: Optional[float] = Field(None, description="Premium received from trade")
    status: Literal["Open", "Active", "Closed"] = Field("Open", description="Trade status")  # <-- Accept "Open"
    call_put: Optional[str] = Field(None, description="Call or Put")  # <-- New field

class WheelStrategyCreate(WheelStrategyBase):
    pass

class WheelStrategyRead(WheelStrategyBase):
    id: int

    class Config:
        orm_mode = True