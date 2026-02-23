"""
Dashboard Router

Provides a consolidated snapshot of portfolio metrics for the UI.
This avoids multiple client calls and centralizes calculation logic.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, UTC
from typing import Dict, Any

from ..database import get_db
from ..dependencies import require_authenticated_user
from .. import models
from ..crud import get_stocks, get_options
from ..services.price_service import fetch_option_contract_price

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_authenticated_user)],
)


@router.get("/snapshot")
def snapshot(db: Session = Depends(get_db)) -> Dict[str, Any]:
    # Load positions with price refresh to populate current prices best-effort
    stocks = get_stocks(db, refresh_prices=True, limit=10000)
    options = get_options(db, refresh_prices=True)

    # Stocks metrics (value from current prices only; no fallback to cost basis)
    open_stocks = [s for s in stocks if (s.status or "Open").lower() == "open"]
    stocks_total_value = 0.0
    stocks_invested_basis = 0.0
    for s in open_stocks:
        price = s.current_price if s.current_price is not None else 0.0
        shares = float(s.shares or 0)
        stocks_total_value += shares * float(price or 0.0)
        stocks_invested_basis += shares * float(s.cost_basis or 0.0)

    # Options metrics (value from current/market prices only; no fallback to cost basis)
    open_options = [o for o in options if (o.status or "Open").lower() == "open"]
    options_total_value = 0.0
    options_invested_basis = 0.0
    for o in open_options:
        contracts = float(o.contracts or 0)
        # Try to fetch exact lastPrice from yfinance option chain
        precise_px = None
        try:
            if o.ticker and o.expiry_date and o.option_type and o.strike_price:
                precise_px = fetch_option_contract_price(
                    o.ticker,
                    o.expiry_date,
                    o.option_type,
                    o.strike_price,
                )
        except Exception:
            precise_px = None
        px = precise_px if precise_px is not None else (o.market_price_per_contract if o.market_price_per_contract is not None else 0.0)
        options_total_value += contracts * float(px or 0.0) * 100.0
        options_invested_basis += contracts * float(o.cost_basis or 0.0) * 100.0

    # Wheels metrics
    # Note: WheelCycle model doesn't have status field, so getting all cycles for now
    open_cycles_q = db.query(models.WheelCycle)
    open_cycles = open_cycles_q.all()
    cycle_ids = [c.id for c in open_cycles]
    total_collateral = 0.0
    if cycle_ids:
        open_puts = (
            db.query(models.WheelEvent)
            .filter(models.WheelEvent.cycle_id.in_(cycle_ids))
            .filter(models.WheelEvent.event_type == "SELL_PUT_OPEN")
            .all()
        )
        for e in open_puts:
            if e.contracts and e.strike:
                total_collateral += float(e.contracts) * float(e.strike) * 100.0

    # Totals & P/L
    portfolio_total_value = stocks_total_value + options_total_value
    total_invested_basis = stocks_invested_basis + options_invested_basis
    # Best-effort unrealized P/L based on current vs. cost basis
    total_pl = (stocks_total_value - stocks_invested_basis) + (options_total_value - options_invested_basis)
    pl_percent = (total_pl / total_invested_basis * 100.0) if total_invested_basis > 0 else None

    active_positions = len(open_stocks) + len(open_options) + len(open_cycles)

    return {
        "as_of": datetime.now(UTC).isoformat(),
        "stocks": {
            "open_count": len(open_stocks),
            "total_value": stocks_total_value,
            "invested_basis": stocks_invested_basis,
        },
        "options": {
            "open_count": len(open_options),
            "total_value": options_total_value,
            "invested_basis": options_invested_basis,
        },
        "wheels": {
            "open_cycles": len(open_cycles),
            "total_collateral": total_collateral,
        },
        "portfolio": {
            "total_value": portfolio_total_value,
            "total_pl": total_pl,
            "pl_percent": pl_percent,
            "active_positions": active_positions,
        },
    }