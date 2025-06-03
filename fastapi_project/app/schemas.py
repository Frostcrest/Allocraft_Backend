from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date


class StockBase(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol")
    shares: float = Field(..., description="Number of shares owned")
    cost_basis: float = Field(..., description="Cost per share")
    market_price: Optional[float] = Field(None, description="Current market price per share")
    status: Literal["Open", "Sold"] = Field("Open", description="Position status")
    entry_date: Optional[date] = Field(None, description="Date position was opened")

class StockCreate(StockBase):
    pass

class StockRead(StockBase):
    id: int

    class Config:
        orm_mode = True

class OptionPositionBase(BaseModel):
    symbol: str
    option_type: str
    strike_price: float
    expiration_date: str
    quantity: int

class OptionPositionCreate(OptionPositionBase):
    pass

class OptionPositionRead(OptionPositionBase):
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