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
    cost: float = Field(..., description="Total premium paid/received")
    market_price_per_contract: Optional[float] = Field(None, description="Current market price per contract")
    status: Literal["Open", "Closed"] = Field("Open", description="Contract status")

class OptionCreate(OptionBase):
    pass

class OptionRead(OptionBase):
    id: int

    class Config:
        orm_mode = True

class LEAPBase(BaseModel):
    ticker: str = Field(..., description="Underlying stock ticker")
    contract_info: str = Field(..., description="Strike, expiry, type description (e.g., '$150 Call Jan 2026')")
    cost: float = Field(..., description="Premium paid for contract")
    current_price: Optional[float] = Field(None, description="Current market value of contract")
    expiry_date: date = Field(..., description="Contract expiration date")

class LEAPCreate(LEAPBase):
    pass

class LEAPRead(LEAPBase):
    id: int

    class Config:
        orm_mode = True