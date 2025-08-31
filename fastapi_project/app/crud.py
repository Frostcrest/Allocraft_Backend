from .utils.security import hash_password, verify_password
from sqlalchemy.orm import Session
from fastapi import HTTPException
from datetime import datetime, UTC

from . import schemas
from . import models
from .models import Ticker, Stock, Price  # Import specific models directly
from .services.price_service import (
    fetch_latest_price,
    fetch_yf_price,
    fetch_option_contract_price,
    fetch_ticker_info,
)

def get_ticker_by_symbol(db: Session, symbol: str):
    """
    Retrieve a ticker by its symbol.
    """
    return db.query(Ticker).filter(Ticker.symbol == symbol).first()

def create_ticker(db: Session, symbol: str) -> Ticker:
    """
    Create and persist a new ticker by symbol.
    If it already exists, returns the existing ticker.
    """
    existing = get_ticker_by_symbol(db, symbol)
    if existing:
        return existing
    ticker_data = fetch_ticker_info(symbol)
    if not ticker_data or not ticker_data.get("symbol"):
        raise HTTPException(status_code=404, detail=f"Ticker '{symbol}' not found.")
    db_ticker = Ticker(**ticker_data)
    db.add(db_ticker)
    db.commit()
    db.refresh(db_ticker)
    return db_ticker

def get_tickers(db: Session, skip: int = 0, limit: int = 100):
    """
    Retrieve a list of tickers with pagination.
    """
    return db.query(Ticker).offset(skip).limit(limit).all()

def get_ticker_by_id(db: Session, ticker_id: int):
    """
    Retrieve a ticker by its primary key ID.
    """
    return db.query(Ticker).filter(Ticker.id == ticker_id).first()

def delete_ticker(db: Session, ticker_id: int):
    """
    Delete a ticker by its ID. Returns True if deleted.
    """
    db_ticker = db.query(Ticker).filter(Ticker.id == ticker_id).first()
    if not db_ticker:
        return False
    db.delete(db_ticker)
    db.commit()
    return True

def create_price(db: Session, price: float, ticker_id: int, timestamp: datetime = None):
    """
    Create and persist a new price for a ticker.
    """
    if timestamp is None:
        timestamp = datetime.now(UTC)
    db_price = models.Price(
        price=price,
        ticker_id=ticker_id,
        timestamp=timestamp
    )
    db.add(db_price)
    db.commit()
    db.refresh(db_price)
    return db_price

def get_prices_for_ticker(db: Session, ticker_id: int, skip: int = 0, limit: int = 100):
    """
    Retrieve prices for a given ticker with pagination.
    """
    return (
        db.query(models.Price)
        .filter(models.Price.ticker_id == ticker_id)
        .order_by(models.Price.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_latest_price_for_ticker(db: Session, ticker_id: int):
    """
    Retrieve the latest price for a given ticker.
    """
    return (
        db.query(models.Price)
        .filter(models.Price.ticker_id == ticker_id)
        .order_by(models.Price.timestamp.desc())
        .first()
    )

def update_ticker_price(db: Session, symbol: str):
    """
    Fetch the latest price for a ticker and store it in the database.
    """
    ticker = get_ticker_by_symbol(db, symbol)
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker '{symbol}' not found.")
    latest_price = fetch_latest_price(symbol)
    if latest_price is None:
        raise HTTPException(status_code=400, detail=f"Could not fetch latest price for '{symbol}'.")
    return create_price(db, price=latest_price, ticker_id=ticker.id)

def get_option_contract_price(db: Session, symbol: str, contract_symbol: str):
    """
    Fetch the latest price for an option contract.
    """
    price = fetch_option_contract_price(symbol, contract_symbol)
    if price is None:
        raise HTTPException(status_code=404, detail=f"Option contract '{contract_symbol}' not found for '{symbol}'.")
    return price

def get_yf_price(db: Session, symbol: str):
    """
    Fetch the latest price for a ticker using yfinance.
    """
    price = fetch_yf_price(symbol)
    if price is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch yfinance price for '{symbol}'.")
    return price

# --- STOCK CRUD FUNCTIONS ---

def get_stocks(db: Session, refresh_prices: bool = False, skip: int = 0, limit: int = 1000):
    """
    Retrieve stock positions with optional pagination.
    If refresh_prices is True, fetch latest prices for Open positions and populate current_price.
    """
    q = db.query(models.Stock)
    if skip:
        q = q.offset(skip)
    if limit:
        q = q.limit(limit)
    items = q.all()
    if refresh_prices:
        changed = False
        for s in items:
            if (s.status or "Open").lower() == "open":
                try:
                    symbol = (s.ticker or "").strip().upper()
                    # Primary: yfinance
                    price = fetch_yf_price(symbol)
                    # Fallback: Twelve Data (requires API key)
                    if price is None:
                        price = fetch_latest_price(symbol)
                    if price is not None:
                        s.current_price = float(price)
                        s.price_last_updated = datetime.now(UTC)
                        changed = True
                except Exception:
                    # Best effort; continue on failure
                    continue
        if changed:
            try:
                db.commit()
            except Exception:
                db.rollback()
    return items

def create_stock(db: Session, stock: schemas.StockCreate):
    """
    Create and persist a new stock position.
    """
    db_stock = models.Stock(**stock.model_dump())
    db.add(db_stock)
    db.commit()
    db.refresh(db_stock)
    return db_stock

def update_stock(db: Session, stock_id: int, stock: schemas.StockCreate):
    """
    Update an existing stock position.
    """
    db_stock = db.query(models.Stock).filter(models.Stock.id == stock_id).first()
    if not db_stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    for key, value in stock.model_dump().items():
        setattr(db_stock, key, value)
    db.commit()
    db.refresh(db_stock)
    return db_stock

def delete_stock(db: Session, stock_id: int):
    """
    Delete a stock position by its ID.
    """
    db_stock = db.query(models.Stock).filter(models.Stock.id == stock_id).first()
    if not db_stock:
        return False
    db.delete(db_stock)
    db.commit()
    return True

# --- OPTION CRUD FUNCTIONS ---

def get_options(db: Session, refresh_prices: bool = False):
    """
    Retrieve all option contracts. If refresh_prices is True, attempt to refresh market_price_per_contract.
    """
    items = db.query(models.Option).all()
    if not refresh_prices:
        return items
    changed = False
    for o in items:
        if (o.status or "Open").lower() != "open":
            continue
        try:
            # Reuse yfinance via high-level helper if available; otherwise best-effort skip
            # We don't have the contract symbol directly, so skip precise lookup and fallback to underlying last price as a proxy
            # For better accuracy, store contract symbol in model in the future and fetch exact lastPrice.
            px = fetch_yf_price((o.ticker or "").upper())
            if px is not None:
                # This is not exact option premium; treat as placeholder only if none set
                if o.market_price_per_contract is None:
                    o.market_price_per_contract = float(px) * 0.01  # naive proxy 1% of underlying
                    changed = True
        except Exception:
            continue
    if changed:
        try:
            db.commit()
        except Exception:
            db.rollback()
    return items

def create_option(db: Session, option: schemas.OptionCreate):
    """
    Create and persist a new option contract.
    """
    db_option = models.Option(**option.model_dump())
    db.add(db_option)
    db.commit()
    db.refresh(db_option)
    return db_option

def update_option(db: Session, option_id: int, option: schemas.OptionCreate):
    """
    Update an existing option contract.
    """
    db_option = db.query(models.Option).filter(models.Option.id == option_id).first()
    if not db_option:
        raise HTTPException(status_code=404, detail="Option not found")
    for key, value in option.model_dump().items():
        setattr(db_option, key, value)
    db.commit()
    db.refresh(db_option)
    return db_option

def delete_option(db: Session, option_id: int):
    """
    Delete an option contract by its ID.
    """
    db_option = db.query(models.Option).filter(models.Option.id == option_id).first()
    if not db_option:
        return False
    db.delete(db_option)
    db.commit()
    return True

# --- WHEEL STRATEGY CRUD FUNCTIONS ---

def get_wheels(db: Session):
    """
    Retrieve all wheel strategies.
    """
    return db.query(models.WheelStrategy).all()

def create_wheel(db: Session, wheel: schemas.WheelStrategyCreate):
    db_wheel = models.WheelStrategy(**wheel.model_dump())
    db.add(db_wheel)
    db.commit()
    db.refresh(db_wheel)
    return db_wheel

def update_wheel(db: Session, wheel_id: int, wheel: schemas.WheelStrategyCreate):
    db_wheel = db.query(models.WheelStrategy).filter(models.WheelStrategy.id == wheel_id).first()
    if not db_wheel:
        raise HTTPException(status_code=404, detail="Wheel strategy not found")
    for key, value in wheel.model_dump().items():
        setattr(db_wheel, key, value)
    db.commit()
    db.refresh(db_wheel)
    return db_wheel

def delete_wheel(db: Session, wheel_id: int):
    """
    Delete a wheel strategy by its ID.
    """
    db_wheel = db.query(models.WheelStrategy).filter(models.WheelStrategy.id == wheel_id).first()
    if not db_wheel:
        return False
    db.delete(db_wheel)
    db.commit()
    return True

# --- USER CRUD FUNCTIONS ---

def get_user_by_username(db: Session, username: str):
    """
    Retrieve a user by their username.
    """
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_email(db: Session, email: str):
    """
    Retrieve a user by their email.
    """
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    """
    Create a new user with hashed password.
    """
    db_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=hash_password(user.password),
        is_active=True,
        roles="user"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, username: str, password: str):
    """
    Authenticate a user by username and password.
    Returns the user if authentication is successful, else None.
    """
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user

def user_has_role(user: models.User, role: str) -> bool:
    """
    Check if the user has a specific role.
    """
    if not user or not user.roles:
        return False
    return role in [r.strip() for r in user.roles.split(",")]

# --- USER ADMIN FUNCTIONS ---

def list_users(db: Session):
    return db.query(models.User).all()

def update_user(db: Session, user_id: int, update: schemas.UserUpdate):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Uniqueness checks for username/email if changing
    if update.username and update.username != user.username:
        if get_user_by_username(db, update.username):
            raise HTTPException(status_code=400, detail="Username already in use")
        user.username = update.username
    if update.email and update.email != user.email:
        if get_user_by_email(db, update.email):
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = update.email
    if update.password:
        user.hashed_password = hash_password(update.password)
    if update.is_active is not None:
        user.is_active = update.is_active
    if update.roles is not None:
        user.roles = update.roles

    db.commit()
    db.refresh(user)
    return user

def delete_user(db: Session, user_id: int) -> bool:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True

# --- EVENT-BASED WHEEL CRUD & METRICS ---

def list_wheel_cycles(db: Session):
    return db.query(models.WheelCycle).all()

def get_wheel_cycle(db: Session, cycle_id: int):
    return db.query(models.WheelCycle).filter(models.WheelCycle.id == cycle_id).first()

def create_wheel_cycle(db: Session, payload: schemas.WheelCycleCreate):
    cycle = models.WheelCycle(**payload.model_dump())
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle

def update_wheel_cycle(db: Session, cycle_id: int, payload: schemas.WheelCycleCreate):
    cycle = get_wheel_cycle(db, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Wheel cycle not found")
    for k, v in payload.model_dump().items():
        setattr(cycle, k, v)
    db.commit()
    db.refresh(cycle)
    return cycle

def delete_wheel_cycle(db: Session, cycle_id: int) -> bool:
    cycle = get_wheel_cycle(db, cycle_id)
    if not cycle:
        return False
    # Also delete events
    db.query(models.WheelEvent).filter(models.WheelEvent.cycle_id == cycle_id).delete()
    db.delete(cycle)
    db.commit()
    return True

def list_wheel_events(db: Session, cycle_id: int | None = None):
    q = db.query(models.WheelEvent)
    if cycle_id is not None:
        q = q.filter(models.WheelEvent.cycle_id == cycle_id)
    return q.order_by(models.WheelEvent.trade_date.asc(), models.WheelEvent.id.asc()).all()

def get_wheel_event(db: Session, event_id: int):
    return db.query(models.WheelEvent).filter(models.WheelEvent.id == event_id).first()

def create_wheel_event(db: Session, payload: schemas.WheelEventCreate):
    # Validate cycle exists
    cycle = get_wheel_cycle(db, payload.cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Wheel cycle not found")
    evt = models.WheelEvent(**payload.model_dump())
    db.add(evt)
    db.commit()
    db.refresh(evt)
    return evt

def update_wheel_event(db: Session, event_id: int, payload: schemas.WheelEventCreate):
    evt = get_wheel_event(db, event_id)
    if not evt:
        raise HTTPException(status_code=404, detail="Wheel event not found")
    for k, v in payload.model_dump().items():
        setattr(evt, k, v)
    db.commit()
    db.refresh(evt)
    return evt

def delete_wheel_event(db: Session, event_id: int) -> bool:
    evt = get_wheel_event(db, event_id)
    if not evt:
        return False
    db.delete(evt)
    db.commit()
    return True


def calculate_wheel_metrics(db: Session, cycle_id: int) -> schemas.WheelMetricsRead:
    cycle = get_wheel_cycle(db, cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail="Wheel cycle not found")
    events = list_wheel_events(db, cycle_id)

    shares_owned = 0.0
    total_cost = 0.0  # dollars invested in shares (buys positive, sells reduce)
    net_options_cashflow = 0.0  # premiums received minus paid, minus fees
    realized_stock_pl = 0.0  # realized P/L from selling shares and called away

    for e in events:
        qty = e.quantity_shares or 0
        contracts = e.contracts or 0
        fees = e.fees or 0
        if e.event_type == "BUY_SHARES":
            # buying increases shares and increases total_cost
            shares_owned += qty
            total_cost += (e.price or 0) * qty + fees
        elif e.event_type == "SELL_SHARES":
            # selling decreases shares, realize P/L relative to average cost
            if qty > 0 and shares_owned > 0:
                avg_cost = (total_cost / shares_owned) if shares_owned else 0.0
                realized_stock_pl += ((e.price or 0) - avg_cost) * qty - fees
                shares_owned -= qty
                total_cost -= avg_cost * qty
        elif e.event_type == "ASSIGNMENT":
            # assignment increases shares at strike
            shares_owned += qty
            total_cost += (e.strike or 0) * qty + fees
        elif e.event_type == "CALLED_AWAY":
            # called away sells shares at strike
            if qty > 0 and shares_owned > 0:
                avg_cost = (total_cost / shares_owned) if shares_owned else 0.0
                realized_stock_pl += ((e.strike or 0) - avg_cost) * qty - fees
                shares_owned -= qty
                total_cost -= avg_cost * qty
        elif e.event_type == "SELL_PUT_OPEN":
            # receive premium
            net_options_cashflow += (e.premium or 0) * contracts * 100 - fees
        elif e.event_type in ("SELL_PUT_CLOSE", "BUY_PUT_CLOSE"):
            # pay to close (negative cashflow)
            net_options_cashflow -= (e.premium or 0) * contracts * 100 + fees
        elif e.event_type == "SELL_CALL_OPEN":
            net_options_cashflow += (e.premium or 0) * contracts * 100 - fees
        elif e.event_type == "SELL_CALL_CLOSE":
            net_options_cashflow -= (e.premium or 0) * contracts * 100 + fees

    average_cost = (total_cost / shares_owned) if shares_owned else 0.0
    total_realized_pl = realized_stock_pl + net_options_cashflow

    # Try to get current price: prefer yfinance, else Twelve Data (if configured), else last stored price or None
    current_price = None
    try:
        p = fetch_yf_price(cycle.ticker)
        if p is not None:
            current_price = float(p)
    except Exception:
        current_price = None
    if current_price is None:
        try:
            p2 = fetch_latest_price(cycle.ticker)
            if p2 is not None:
                current_price = float(p2)
        except Exception:
            pass
    if current_price is None:
        try:
            t = get_ticker_by_symbol(db, cycle.ticker)
            if t and t.last_price is not None:
                current_price = float(t.last_price)
        except Exception:
            pass

    unrealized_pl = 0.0
    if current_price is not None and shares_owned:
        unrealized_pl = (current_price - average_cost) * shares_owned

    return schemas.WheelMetricsRead(
        cycle_id=cycle_id,
        ticker=cycle.ticker,
        shares_owned=round(shares_owned, 6),
        average_cost_basis=round(average_cost, 6),
        total_cost_remaining=round(total_cost, 2),
        net_options_cashflow=round(net_options_cashflow, 2),
        realized_stock_pl=round(realized_stock_pl, 2),
        total_realized_pl=round(total_realized_pl, 2),
        current_price=current_price if current_price is None else round(current_price, 4),
        unrealized_pl=round(unrealized_pl, 2),
    )


# --- LOTS: CRUD, METRICS, ASSEMBLER ---
from typing import List, Optional


def list_lots(db: Session, cycle_id: int | None = None, ticker: str | None = None, status: str | None = None, covered: bool | None = None) -> List[models.Lot]:
    q = db.query(models.Lot)
    if cycle_id is not None:
        q = q.filter(models.Lot.cycle_id == cycle_id)
    if ticker is not None:
        q = q.filter(models.Lot.ticker == ticker)
    if status is not None:
        q = q.filter(models.Lot.status == status)
    if covered is True:
        q = q.filter(models.Lot.status == "OPEN_COVERED")
    if covered is False:
        q = q.filter(models.Lot.status == "OPEN_UNCOVERED")
    return q.order_by(models.Lot.id.desc()).all()


def get_lot(db: Session, lot_id: int) -> models.Lot | None:
    return db.query(models.Lot).filter(models.Lot.id == lot_id).first()


def create_lot(db: Session, payload: schemas.LotCreate) -> models.Lot:
    lot = models.Lot(**payload.model_dump())
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return lot


def update_lot(db: Session, lot_id: int, payload: schemas.LotUpdate) -> models.Lot | None:
    lot = get_lot(db, lot_id)
    if not lot:
        return None
    allowed = {"status", "notes", "cost_basis_effective", "acquisition_date"}
    for k, v in payload.model_dump(exclude_unset=True).items():
        if k in allowed:
            setattr(lot, k, v)
    db.commit()
    db.refresh(lot)
    return lot


def delete_lot(db: Session, lot_id: int) -> bool:
    lot = get_lot(db, lot_id)
    if not lot:
        return False
    db.query(models.LotLink).filter(models.LotLink.lot_id == lot_id).delete()
    db.query(models.LotMetrics).filter(models.LotMetrics.lot_id == lot_id).delete()
    db.delete(lot)
    db.commit()
    return True


def list_lot_links(db: Session, lot_id: int) -> List[models.LotLink]:
    return db.query(models.LotLink).filter(models.LotLink.lot_id == lot_id).all()


def create_lot_link(db: Session, payload: schemas.LotLinkCreate) -> models.LotLink:
    link = models.LotLink(**payload.model_dump())
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def delete_lot_link(db: Session, link_id: int) -> bool:
    link = db.query(models.LotLink).filter(models.LotLink.id == link_id).first()
    if not link:
        return False
    db.delete(link)
    db.commit()
    return True


def refresh_lot_metrics(db: Session, lot_id: int) -> schemas.LotMetricsRead:
    lot = get_lot(db, lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    links = list_lot_links(db, lot_id)
    linked_event_ids = [l.linked_object_id for l in links if l.linked_object_type == "WHEEL_EVENT"]
    events = []
    if linked_event_ids:
        events = (
            db.query(models.WheelEvent)
            .filter(models.WheelEvent.id.in_(linked_event_ids))
            .all()
        )

    net_premiums = 0.0
    stock_cost_total = 0.0
    fees_total = 0.0
    realized_pl = 0.0

    # Track shares to infer coverage status
    shares_remaining = 0
    for e in events:
        fees = e.fees or 0.0
        fees_total += fees
        et = e.event_type
        contracts = e.contracts or 0
        qty = e.quantity_shares or 0
        if et in ("SELL_PUT_OPEN", "SELL_CALL_OPEN"):
            net_premiums += (e.premium or 0) * contracts * 100
        elif et in ("SELL_PUT_CLOSE", "SELL_CALL_CLOSE"):
            net_premiums -= (e.premium or 0) * contracts * 100
        elif et in ("BUY_SHARES", "ASSIGNMENT"):
            stock_cost_total += (e.price or e.strike or 0) * qty
            shares_remaining += qty
        elif et in ("SELL_SHARES", "CALLED_AWAY"):
            # realized component relative to effective basis calculated later; here treat as stock proceeds
            stock_cost_total -= (e.price or e.strike or 0) * qty
            shares_remaining -= qty

    # Effective cost basis per lot (100 shares)
    cost_basis_effective = None
    try:
        cost_basis_effective = (stock_cost_total - net_premiums + fees_total) / 100.0
    except Exception:
        cost_basis_effective = None

    lot.cost_basis_effective = cost_basis_effective
    # Auto-fix coverage status: if shares < 100, lot cannot be covered
    try:
        if shares_remaining < 100 and lot.status == "OPEN_COVERED":
            lot.status = "OPEN_UNCOVERED"
        # If exactly zero and there was a CALLED_AWAY event, prefer closed_called_away; otherwise leave as uncovered
        if shares_remaining <= 0:
            if any(e.event_type == "CALLED_AWAY" for e in events):
                lot.status = "CLOSED_CALLED_AWAY"
            else:
                # Keep uncovered per product requirement rather than auto-closing as SOLD
                if lot.status not in ("CLOSED_CALLED_AWAY", "CLOSED_SOLD"):
                    lot.status = "OPEN_UNCOVERED"
    except Exception:
        pass
    db.commit()

    # Unrealized P/L estimate (stock-only)
    unrealized_pl = 0.0
    current_price = None
    try:
        if lot.ticker:
            p = fetch_yf_price(lot.ticker)
            if p is not None:
                current_price = float(p)
    except Exception:
        current_price = None
    if current_price is None and lot.ticker:
        try:
            p2 = fetch_latest_price(lot.ticker)
            if p2 is not None:
                current_price = float(p2)
        except Exception:
            pass
    # If lot is closed, unrealized is zero
    if lot.status in ("CLOSED_CALLED_AWAY", "CLOSED_SOLD", "CLOSED_MERGED"):
        unrealized_pl = 0.0
    elif current_price is not None and cost_basis_effective is not None:
        unrealized_pl = (current_price - cost_basis_effective) * 100.0

    # Upsert metrics row
    m = db.query(models.LotMetrics).filter(models.LotMetrics.lot_id == lot_id).first()
    if not m:
        m = models.LotMetrics(lot_id=lot_id)
        db.add(m)
    m.net_premiums = round(net_premiums, 2)
    m.stock_cost_total = round(stock_cost_total, 2)
    m.fees_total = round(fees_total, 2)
    m.realized_pl = round(realized_pl, 2)
    m.unrealized_pl = round(unrealized_pl, 2)
    db.commit()

    return schemas.LotMetricsRead(
        lot_id=lot_id,
        net_premiums=m.net_premiums,
        stock_cost_total=m.stock_cost_total,
        fees_total=m.fees_total,
        realized_pl=m.realized_pl,
        unrealized_pl=m.unrealized_pl,
    )


class LotAssembler:
    """Deterministically groups WheelEvents into 100-share lots.

    v1 assumptions:
    - 1 assignment event equals 100 shares acquired.
    - BUY_SHARES accumulate into 100-share chunks.
    - SELL_CALL_OPEN binds to oldest OPEN_UNCOVERED lot.
    """

    def __init__(self, db: Session):
        self.db = db

    def rebuild_for_cycle(self, cycle_id: int) -> List[models.Lot]:
        # Purge existing
        existing_lots = self.db.query(models.Lot).filter(models.Lot.cycle_id == cycle_id).all()
        for lot in existing_lots:
            self.db.query(models.LotLink).filter(models.LotLink.lot_id == lot.id).delete()
            self.db.query(models.LotMetrics).filter(models.LotMetrics.lot_id == lot.id).delete()
        self.db.query(models.Lot).filter(models.Lot.cycle_id == cycle_id).delete()
        self.db.commit()

        cycle = self.db.query(models.WheelCycle).filter(models.WheelCycle.id == cycle_id).first()
        ticker = cycle.ticker if cycle else None
        events = (
            self.db.query(models.WheelEvent)
            .filter(models.WheelEvent.cycle_id == cycle_id)
            .order_by(models.WheelEvent.trade_date.asc(), models.WheelEvent.id.asc())
            .all()
        )

        shares_buffer = 0
        created: List[models.Lot] = []
        to_refresh_metrics: list[int] = []

        for e in events:
            et = e.event_type
            if et == "ASSIGNMENT":
                lot = models.Lot(
                    cycle_id=cycle_id,
                    ticker=ticker,
                    acquisition_method="PUT_ASSIGNMENT",
                    acquisition_date=e.trade_date,
                    status="OPEN_UNCOVERED",
                )
                self.db.add(lot)
                self.db.flush()
                self.db.refresh(lot)
                created.append(lot)
                self.db.add(models.LotLink(lot_id=lot.id, linked_object_type="WHEEL_EVENT", linked_object_id=e.id, role="PUT_ASSIGNMENT"))
                self.db.add(models.LotMetrics(lot_id=lot.id))
                to_refresh_metrics.append(lot.id)
            elif et == "BUY_SHARES":
                shares_buffer += int(e.quantity_shares or 0)
                while shares_buffer >= 100:
                    lot = models.Lot(
                        cycle_id=cycle_id,
                        ticker=ticker,
                        acquisition_method="OUTRIGHT_PURCHASE",
                        acquisition_date=e.trade_date,
                        status="OPEN_UNCOVERED",
                    )
                    self.db.add(lot)
                    self.db.flush()
                    self.db.refresh(lot)
                    created.append(lot)
                    self.db.add(models.LotLink(lot_id=lot.id, linked_object_type="WHEEL_EVENT", linked_object_id=e.id, role="STOCK_BUY"))
                    self.db.add(models.LotMetrics(lot_id=lot.id))
                    to_refresh_metrics.append(lot.id)
                    shares_buffer -= 100
            elif et == "SELL_SHARES":
                # If user sold shares, first uncover covered lots (removing coverage),
                # then close uncovered lots if more 100-share chunks were sold.
                qty = int(e.quantity_shares or 0)
                # consume covered lots -> uncovered
                while qty >= 100:
                    covered_lot = (
                        self.db.query(models.Lot)
                        .filter(models.Lot.cycle_id == cycle_id, models.Lot.status == "OPEN_COVERED")
                        .order_by(models.Lot.id.asc())
                        .first()
                    )
                    if not covered_lot:
                        break
                    self.db.add(models.LotLink(lot_id=covered_lot.id, linked_object_type="WHEEL_EVENT", linked_object_id=e.id, role="STOCK_SELL"))
                    covered_lot.status = "OPEN_UNCOVERED"
                    to_refresh_metrics.append(covered_lot.id)
                    qty -= 100
                # if still selling more, close open-uncovered lots as SOLD
                while qty >= 100:
                    open_lot = (
                        self.db.query(models.Lot)
                        .filter(models.Lot.cycle_id == cycle_id, models.Lot.status == "OPEN_UNCOVERED")
                        .order_by(models.Lot.id.asc())
                        .first()
                    )
                    if not open_lot:
                        break
                    self.db.add(models.LotLink(lot_id=open_lot.id, linked_object_type="WHEEL_EVENT", linked_object_id=e.id, role="STOCK_SELL"))
                    open_lot.status = "CLOSED_SOLD"
                    to_refresh_metrics.append(open_lot.id)
                    qty -= 100
                # Remainder < 100 shares sold: uncover one covered lot or record partial sell on an open lot
                if qty > 0:
                    covered_lot = (
                        self.db.query(models.Lot)
                        .filter(models.Lot.cycle_id == cycle_id, models.Lot.status == "OPEN_COVERED")
                        .order_by(models.Lot.id.asc())
                        .first()
                    )
                    if covered_lot:
                        self.db.add(models.LotLink(lot_id=covered_lot.id, linked_object_type="WHEEL_EVENT", linked_object_id=e.id, role="STOCK_SELL"))
                        covered_lot.status = "OPEN_UNCOVERED"
                        to_refresh_metrics.append(covered_lot.id)
                    else:
                        open_lot = (
                            self.db.query(models.Lot)
                            .filter(models.Lot.cycle_id == cycle_id, models.Lot.status == "OPEN_UNCOVERED")
                            .order_by(models.Lot.id.asc())
                            .first()
                        )
                        if open_lot:
                            self.db.add(models.LotLink(lot_id=open_lot.id, linked_object_type="WHEEL_EVENT", linked_object_id=e.id, role="STOCK_SELL"))
                            to_refresh_metrics.append(open_lot.id)
            elif et == "SELL_CALL_OPEN":
                # bind to oldest open_uncovered lot
                open_lot = (
                    self.db.query(models.Lot)
                    .filter(models.Lot.cycle_id == cycle_id, models.Lot.status == "OPEN_UNCOVERED")
                    .order_by(models.Lot.id.asc())
                    .first()
                )
                if open_lot:
                    self.db.add(models.LotLink(lot_id=open_lot.id, linked_object_type="WHEEL_EVENT", linked_object_id=e.id, role="CALL_OPEN"))
                    open_lot.status = "OPEN_COVERED"
                    to_refresh_metrics.append(open_lot.id)
            elif et == "SELL_CALL_CLOSE":
                covered_lot = (
                    self.db.query(models.Lot)
                    .filter(models.Lot.cycle_id == cycle_id, models.Lot.status == "OPEN_COVERED")
                    .order_by(models.Lot.id.asc())
                    .first()
                )
                if covered_lot:
                    self.db.add(models.LotLink(lot_id=covered_lot.id, linked_object_type="WHEEL_EVENT", linked_object_id=e.id, role="CALL_CLOSE"))
                    covered_lot.status = "OPEN_UNCOVERED"
                    to_refresh_metrics.append(covered_lot.id)
            elif et == "CALLED_AWAY":
                # Prefer closing a covered lot; if none, close an uncovered lot that previously had a call open linked.
                lot_to_close = (
                    self.db.query(models.Lot)
                    .filter(models.Lot.cycle_id == cycle_id, models.Lot.status == "OPEN_COVERED")
                    .order_by(models.Lot.id.asc())
                    .first()
                )
                if not lot_to_close:
                    # find an open uncovered lot that has a CALL_OPEN link lingering (e.g., after a manual unbind/roll)
                    candidate = (
                        self.db.query(models.Lot)
                        .filter(models.Lot.cycle_id == cycle_id)
                        .order_by(models.Lot.id.asc())
                        .all()
                    )
                    for l in candidate:
                        link = (
                            self.db.query(models.LotLink)
                            .filter(models.LotLink.lot_id == l.id, models.LotLink.role == "CALL_OPEN")
                            .first()
                        )
                        if link and l.status in ("OPEN_UNCOVERED", "OPEN_COVERED"):
                            lot_to_close = l
                            break
                if lot_to_close:
                    self.db.add(models.LotLink(lot_id=lot_to_close.id, linked_object_type="WHEEL_EVENT", linked_object_id=e.id, role="CALL_ASSIGNMENT"))
                    lot_to_close.status = "CLOSED_CALLED_AWAY"
                    to_refresh_metrics.append(lot_to_close.id)

        # Single commit for all changes
        self.db.commit()

        # Refresh metrics post-commit in a stable state
        for lot_id in to_refresh_metrics:
            try:
                refresh_lot_metrics(self.db, lot_id)
            except Exception:
                # Don’t fail the entire rebuild on a single metrics issue
                pass
        return created


def rebuild_lots_for_cycle(db: Session, cycle_id: int) -> List[models.Lot]:
    assembler = LotAssembler(db)
    return assembler.rebuild_for_cycle(cycle_id)