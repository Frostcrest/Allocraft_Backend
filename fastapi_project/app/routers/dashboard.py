"""
Dashboard Router

Provides a consolidated snapshot of portfolio metrics for the UI.
This avoids multiple client calls and centralizes calculation logic.

Performance notes:
- GET /snapshot uses DB-cached prices (refresh_prices=False) and a 60-second in-memory
  cache so hot-path renders never block on yfinance HTTP calls.
- POST /refresh-prices performs a full price refresh (stocks + options in parallel)
  and populates the snapshot cache; it is rate-limited to 1/minute.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, UTC
from typing import Dict, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_authenticated_user
from .. import models
from ..crud import get_stocks, get_options
from ..services.price_service import fetch_option_contract_price
from ..limiter import limiter

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_authenticated_user)],
)

# ---------------------------------------------------------------------------
# Module-level TTL snapshot cache (single server process; safe for Render).
# All writes are protected by GIL (dict assignment is atomic in CPython).
# ---------------------------------------------------------------------------
_SNAPSHOT_TTL_SECONDS: int = 60
_snapshot_cache: dict = {}  # key -> {"ts": float, "data": dict}


def _build_snapshot(db: Session, *, refresh_prices: bool = False) -> Dict[str, Any]:
    """Compute the full portfolio snapshot dict.

    Args:
        db: Active SQLAlchemy session.
        refresh_prices: When True, stocks and options are refreshed from yfinance
            before metrics are calculated (used by the explicit refresh endpoint).
            Option contract prices are fetched in parallel via ThreadPoolExecutor.
    """
    stocks = get_stocks(db, refresh_prices=refresh_prices, limit=10000)
    options = get_options(db, refresh_prices=refresh_prices)

    # -- Stocks --
    open_stocks = [s for s in stocks if (s.status or "Open").lower() == "open"]
    stocks_total_value = 0.0
    stocks_invested_basis = 0.0
    for s in open_stocks:
        shares = float(s.shares or 0)
        price = float(s.current_price or 0.0)
        stocks_total_value += shares * price
        stocks_invested_basis += shares * float(s.cost_basis or 0.0)

    # -- Options --
    open_options = [o for o in options if (o.status or "Open").lower() == "open"]
    options_total_value = 0.0
    options_invested_basis = 0.0

    if refresh_prices:
        # Fetch option contract prices in parallel (one thread per contract).
        def _fetch_px(opt):
            try:
                if opt.ticker and opt.expiry_date and opt.option_type and opt.strike_price:
                    return opt.id, fetch_option_contract_price(
                        opt.ticker, opt.expiry_date, opt.option_type, opt.strike_price
                    )
            except Exception:
                pass
            return opt.id, None

        precise_prices: Dict[int, Any] = {}
        with ThreadPoolExecutor(max_workers=min(10, len(open_options) or 1)) as pool:
            futures = {pool.submit(_fetch_px, o): o for o in open_options}
            for fut in as_completed(futures):
                opt_id, px = fut.result()
                if px is not None:
                    precise_prices[opt_id] = px
    else:
        precise_prices = {}

    for o in open_options:
        contracts = float(o.contracts or 0)
        px = precise_prices.get(o.id) or o.market_price_per_contract or 0.0
        options_total_value += contracts * float(px) * 100.0
        options_invested_basis += contracts * float(o.cost_basis or 0.0) * 100.0

    # -- Wheels --
    open_cycles = db.query(models.WheelCycle).all()
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

    # -- Portfolio totals --
    portfolio_total_value = stocks_total_value + options_total_value
    total_invested_basis = stocks_invested_basis + options_invested_basis
    total_pl = (
        (stocks_total_value - stocks_invested_basis)
        + (options_total_value - options_invested_basis)
    )
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


@router.get("/snapshot")
@limiter.limit("30/minute")
def snapshot(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return cached portfolio snapshot (stale up to 60 seconds).

    Uses DB-cached prices only — no live yfinance calls on the hot path.
    Call POST /dashboard/refresh-prices to force a live refresh.
    """
    cached = _snapshot_cache.get("snapshot")
    if cached and (time.time() - cached["ts"]) < _SNAPSHOT_TTL_SECONDS:
        return cached["data"]

    data = _build_snapshot(db, refresh_prices=False)
    _snapshot_cache["snapshot"] = {"ts": time.time(), "data": data}
    return data


@router.post("/refresh-prices")
@limiter.limit("1/minute")
def refresh_prices(request: Request, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Trigger a live price refresh from yfinance and repopulate the snapshot cache.

    Option contract prices are fetched in parallel (up to 10 concurrent threads).
    This endpoint is rate-limited to 1 request per minute to avoid yfinance abuse.
    """
    data = _build_snapshot(db, refresh_prices=True)
    _snapshot_cache["snapshot"] = {"ts": time.time(), "data": data}
    return {"status": "refreshed", "as_of": data["as_of"]}
