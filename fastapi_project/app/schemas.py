from pydantic import BaseModel
from typing import Optional


class PositionBase(BaseModel):
    symbol: str
    position_type: str  # 'stock', 'call', 'put'
    quantity: float
    average_price: float
    expiry: Optional[str] = None
    strike_price: Optional[float] = None
    side: Optional[str] = None  # 'long', 'short'

class PositionCreate(PositionBase):
    pass

class PositionRead(PositionBase):
    id: int

    class Config:
        orm_mode = True

# This file defines the Pydantic schemas for the Ticker model.
class TickerBase(BaseModel):
    symbol: str
    name: Optional[str] = None
    last_price: Optional[str] = None
    change: Optional[str] = None
    change_percent: Optional[str] = None
    volume: Optional[str] = None
    market_cap: Optional[str] = None
    timestamp: Optional[str] = None  # You can use datetime if desired

class TickerCreate(BaseModel):
    symbol: str
    
class TickerRead(TickerBase):
    id: int

    class Config:
        orm_mode = True