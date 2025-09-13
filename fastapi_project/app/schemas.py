from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic import ConfigDict
from typing import Optional, Literal, Dict, Any
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

    # Normalize empty strings coming from the DB (stored as TEXT) to None for date fields
    @field_validator("entry_date", mode="before")
    @classmethod
    def _empty_date_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

class StockCreate(StockBase):
    """Schema for creating a new stock position."""
    pass

class StockRead(StockBase):
    """Schema for reading a stock position from the database."""
    id: int

    model_config = ConfigDict(from_attributes=True)  # Pydantic v2 compatible ORM mode

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

    model_config = ConfigDict(from_attributes=True)

# --- OPTION SCHEMAS ---
# These classes define the structure of data for options contracts.

class OptionBase(BaseModel):
    ticker: str = Field(..., description="Underlying stock ticker")
    option_type: Literal["Call", "Put"] = Field(..., description="Type of option contract")
    strike_price: float = Field(..., description="Strike price of the option")
    # Some legacy rows may have empty string in DB; accept None on read
    expiry_date: Optional[date] = Field(None, description="Option expiration date")
    contracts: float = Field(..., description="Number of contracts")
    cost_basis: float = Field(..., description="Cost basis per contract")  # Cost per contract, not total
    market_price_per_contract: Optional[float] = Field(None, description="Current market price per contract")
    status: Literal["Open", "Closed"] = Field("Open", description="Contract status")
    current_price: Optional[float] = Field(None, description="Current price of the underlying")

    @field_validator("expiry_date", mode="before")
    @classmethod
    def _empty_expiry_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

class OptionCreate(OptionBase):
    """Schema for creating a new option contract."""
    pass

class OptionRead(OptionBase):
    """Schema for reading an option contract from the database."""
    id: int

    model_config = ConfigDict(from_attributes=True)

# --- WHEEL STRATEGY SCHEMAS ---
# These classes define the structure of data for wheel strategy trades.

class WheelStrategyBase(BaseModel):
    wheel_id: str
    ticker: str
    trade_date: Optional[date]

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

    model_config = ConfigDict(from_attributes=True)

# --- EVENT-BASED WHEEL SCHEMAS ---

class WheelCycleBase(BaseModel):
    cycle_key: str = Field(..., description="Unique key per wheel cycle, e.g., AAPL-1")
    ticker: str
    started_at: Optional[date] = None
    status: Literal["Open", "Closed"] = "Open"
    notes: Optional[str] = None
    strategy_type: Optional[str] = None
    detection_metadata: Optional[Dict[str, Any]] = None

    @field_validator("started_at", mode="before")
    @classmethod
    def _empty_started_at_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

class WheelCycleCreate(WheelCycleBase):
    pass

class WheelCycleRead(WheelCycleBase):
    id: int
    
    # Real-time P&L fields
    current_option_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    total_pnl: Optional[float] = None
    price_last_updated: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WheelEventBase(BaseModel):
    cycle_id: int
    event_type: Literal[
        "BUY_SHARES",
        "SELL_SHARES",
        "SELL_PUT_OPEN",
        "SELL_PUT_CLOSE",
    "BUY_PUT_CLOSE",
        "ASSIGNMENT",
        "SELL_CALL_OPEN",
        "SELL_CALL_CLOSE",
        "CALLED_AWAY",
    ]
    event_date: Optional[date] = None

    quantity_shares: Optional[float] = None
    contracts: Optional[int] = None
    price: Optional[float] = None
    strike: Optional[float] = None
    premium: Optional[float] = None
    fees: Optional[float] = None

    link_event_id: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("event_date", mode="before")
    @classmethod
    def _empty_event_date_to_none(cls, v):
        if v is None:
            return None
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

class WheelEventCreate(WheelEventBase):
    pass

class WheelEventRead(WheelEventBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class WheelMetricsRead(BaseModel):
    cycle_id: int
    ticker: str
    shares_owned: float
    average_cost_basis: float
    total_cost_remaining: float
    net_options_cashflow: float
    realized_stock_pl: float
    total_realized_pl: float
    current_price: float | None = None
    unrealized_pl: float


# --- Lots ---
class LotBase(BaseModel):
    cycle_id: int
    ticker: str
    acquisition_method: str
    acquisition_date: Optional[str] = None
    status: Optional[str] = Field(default="OPEN_UNCOVERED")
    cost_basis_effective: Optional[float] = None
    notes: Optional[str] = None


class LotCreate(LotBase):
    pass


class LotRead(LotBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LotUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    cost_basis_effective: Optional[float] = None
    acquisition_date: Optional[str] = None


class LotLinkBase(BaseModel):
    lot_id: int
    linked_object_type: str  # e.g., WHEEL_EVENT
    linked_object_id: int
    role: str


class LotLinkCreate(LotLinkBase):
    pass


class LotLinkRead(LotLinkBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class LotMetricsRead(BaseModel):
    lot_id: int
    net_premiums: float = 0.0
    stock_cost_total: float = 0.0
    fees_total: float = 0.0
    realized_pl: float = 0.0
    unrealized_pl: float = 0.0

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

    model_config = ConfigDict(from_attributes=True)

class UserLogin(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
    """Schema for admin updating user details; all fields optional."""
    username: str | None = Field(None, description="New username")
    email: EmailStr | None = Field(None, description="New email")
    password: str | None = Field(None, min_length=6, description="New password (plain)")
    is_active: bool | None = Field(None, description="Activate/deactivate user")
    roles: str | None = Field(None, description="Comma-separated roles, e.g. 'user,admin'")

# --- JWT Token SCHEMAS ---

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    roles: Optional[str] = None