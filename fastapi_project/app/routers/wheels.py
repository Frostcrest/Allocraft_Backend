"""
Wheels Router

Beginner guide:
- These endpoints power the Wheel Strategy views in the UI.
- Two styles exist here:
    1) Legacy CSV-based WheelStrategy CRUD (simple rows)
    2) Event-based model: wheel cycles, wheel events, and lots (recommended)

Contracts (inputs/outputs, simplified):
- GET /wheels/wheel-cycles -> list of WheelCycleRead
- POST /wheels/wheel-cycles { ticker, cycle_key?, ... } -> WheelCycleRead
- GET /wheels/wheel-events?cycle_id=ID -> list of WheelEventRead
- POST /wheels/wheel-events { cycle_id, event_type, trade_date, ... } -> WheelEventRead
- GET /wheels/cycles/{id}/lots -> list of LotRead
- GET /wheels/lots/{id}/metrics -> LotMetricsRead

Common errors:
- 404 when a resource ID doesn’t exist
- 400 when an event payload is invalid (wrong type for bind/unbind)
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .. import schemas, crud, models
from ..models_unified import Position
from ..database import get_db
from ..crud_optimized import BatchLoaderService, MetricsService, refresh_prices_batch
from fastapi.responses import StreamingResponse
import io
import csv
from typing import Optional, Dict, Any, List
from datetime import datetime
import math
from typing import Optional, Dict, Any

router = APIRouter(prefix="/wheels", tags=["Wheels"])

@router.get("/", response_model=list[schemas.WheelStrategyRead])
def read_wheels(db: Session = Depends(get_db)):
    """Get all legacy (CSV-style) wheel strategies.

    Returns: list[WheelStrategyRead]
    """
    return crud.get_wheels(db)

@router.post("/", response_model=schemas.WheelStrategyRead)
def create_wheel(wheel: schemas.WheelStrategyCreate, db: Session = Depends(get_db)):
    """Add a new legacy wheel strategy.

    Input: WheelStrategyCreate
    Returns: WheelStrategyRead
    """
    return crud.create_wheel(db, wheel)

@router.put("/{wheel_id}", response_model=schemas.WheelStrategyRead)
def update_wheel(wheel_id: int, wheel: schemas.WheelStrategyCreate, db: Session = Depends(get_db)):
    """Update an existing legacy wheel strategy by ID.

    Path: wheel_id
    Input: WheelStrategyCreate
    Returns: WheelStrategyRead
    Errors: 404 if not found
    """
    return crud.update_wheel(db, wheel_id, wheel)

@router.delete("/{wheel_id}")
def delete_wheel(wheel_id: int, db: Session = Depends(get_db)):
    """Delete a legacy wheel strategy by ID.

    Returns: { detail: string }
    Errors: 404 if not found
    """
    success = crud.delete_wheel(db, wheel_id)
    if not success:
        raise HTTPException(status_code=404, detail="Wheel strategy not found")
    return {"detail": "Wheel strategy deleted"}

@router.get("/template")
def download_wheels_csv_template():
    """Download a CSV template for legacy wheel strategies."""
    csv_content = (
        "wheel_id,ticker,trade_date,"
        "sell_put_strike_price,sell_put_open_premium,sell_put_closed_premium,sell_put_status,sell_put_quantity,"
        "assignment_strike_price,assignment_shares_quantity,assignment_status,"
        "sell_call_strike_price,sell_call_open_premium,sell_call_closed_premium,sell_call_status,sell_call_quantity,"
        "called_away_strike_price,called_away_shares_quantity,called_away_status\n"
        "AAPL-W1,AAPL,2024-07-19,150,2.50,,Open,1,,,,,,,,,,\n"
        "MSFT-W1,MSFT,2024-08-16,,,,,,320,100,Closed,320,3.10,3.00,Closed,1,320,100,Closed\n"
    )
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=wheels_template.csv"}
    )

@router.post("/upload")
async def upload_wheels_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a CSV file to bulk add legacy wheel strategies.

    Input: multipart/form-data with CSV file
    Returns: { created: number }
    """
    contents = await file.read()
    decoded = contents.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)
    created = []
    for row in reader:
        try:
            db_wheel = models.WheelStrategy(
                wheel_id=row.get("wheel_id") or f"{row['ticker'].strip().upper()}-W",
                ticker=row["ticker"].strip().upper(),
                trade_date=row.get("trade_date"),
                sell_put_strike_price=float(row["sell_put_strike_price"]) if row.get("sell_put_strike_price") else None,
                sell_put_open_premium=float(row["sell_put_open_premium"]) if row.get("sell_put_open_premium") else None,
                sell_put_closed_premium=float(row["sell_put_closed_premium"]) if row.get("sell_put_closed_premium") else None,
                sell_put_status=row.get("sell_put_status"),
                sell_put_quantity=int(row["sell_put_quantity"]) if row.get("sell_put_quantity") else None,
                assignment_strike_price=float(row["assignment_strike_price"]) if row.get("assignment_strike_price") else None,
                assignment_shares_quantity=int(row["assignment_shares_quantity"]) if row.get("assignment_shares_quantity") else None,
                assignment_status=row.get("assignment_status"),
                sell_call_strike_price=float(row["sell_call_strike_price"]) if row.get("sell_call_strike_price") else None,
                sell_call_open_premium=float(row["sell_call_open_premium"]) if row.get("sell_call_open_premium") else None,
                sell_call_closed_premium=float(row["sell_call_closed_premium"]) if row.get("sell_call_closed_premium") else None,
                sell_call_status=row.get("sell_call_status"),
                sell_call_quantity=int(row["sell_call_quantity"]) if row.get("sell_call_quantity") else None,
                called_away_strike_price=float(row["called_away_strike_price"]) if row.get("called_away_strike_price") else None,
                called_away_shares_quantity=int(row["called_away_shares_quantity"]) if row.get("called_away_shares_quantity") else None,
                called_away_status=row.get("called_away_status"),
            )
            db.add(db_wheel)
            created.append(db_wheel)
        except Exception:
            continue
    db.commit()
    return {"created": len(created)}

@router.get("/summary")
def wheels_summary(db: Session = Depends(get_db)):
    """Return a lightweight summary for dashboard cards: number of open cycles and total collateral approximation.

    Collateral approximation: sum over open SELL_PUT_OPEN events' contracts*strike*100 minus any linked closes.
    For now, we compute a naive upper bound: all open SELL_PUT_OPEN in open cycles.
    """
    open_cycles = db.query(models.WheelCycle).filter(models.WheelCycle.status == "Open").all()
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
    return {"open_cycles": len(open_cycles), "total_collateral": total_collateral}


# --- Event-based Wheel endpoints ---

@router.get("/wheel-cycles", response_model=list[schemas.WheelCycleRead])
@router.get("/wheel_cycles", response_model=list[schemas.WheelCycleRead])
def list_wheel_cycles(db: Session = Depends(get_db)):
    """List event-based wheel cycles.

    Returns: list[WheelCycleRead]
    """
    return crud.list_wheel_cycles(db)


@router.post("/wheel-cycles", response_model=schemas.WheelCycleRead)
@router.post("/wheel_cycles", response_model=schemas.WheelCycleRead)
def create_wheel_cycle(payload: schemas.WheelCycleCreate, db: Session = Depends(get_db)):
    """Create a new wheel cycle.

    Input: WheelCycleCreate
    Returns: WheelCycleRead
    """
    return crud.create_wheel_cycle(db, payload)


@router.put("/wheel-cycles/{cycle_id}", response_model=schemas.WheelCycleRead)
@router.put("/wheel_cycles/{cycle_id}", response_model=schemas.WheelCycleRead)
def update_wheel_cycle(cycle_id: int, payload: schemas.WheelCycleCreate, db: Session = Depends(get_db)):
    """Update an existing wheel cycle by ID.

    Path: cycle_id
    Input: WheelCycleCreate
    Returns: WheelCycleRead
    Errors: 404 if not found
    """
    return crud.update_wheel_cycle(db, cycle_id, payload)


@router.delete("/wheel-cycles/{cycle_id}")
@router.delete("/wheel_cycles/{cycle_id}")
def delete_wheel_cycle(cycle_id: int, db: Session = Depends(get_db)):
    """Delete a wheel cycle by ID (also removes its events).

    Returns: { detail: string }
    Errors: 404 if not found
    """
    ok = crud.delete_wheel_cycle(db, cycle_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Wheel cycle not found")
    return {"detail": "Wheel cycle deleted"}


@router.get("/wheel-events", response_model=list[schemas.WheelEventRead])
@router.get("/wheel_events", response_model=list[schemas.WheelEventRead])
def list_wheel_events(cycle_id: int | None = None, db: Session = Depends(get_db)):
    """List wheel events, optionally filtered by cycle_id.

    Query: cycle_id? (int)
    Returns: list[WheelEventRead]
    """
    return crud.list_wheel_events(db, cycle_id)


@router.post("/wheel-events", response_model=schemas.WheelEventRead)
@router.post("/wheel_events", response_model=schemas.WheelEventRead)
def create_wheel_event(payload: schemas.WheelEventCreate, db: Session = Depends(get_db)):
    """Create a wheel event.

    Input: WheelEventCreate
    Returns: WheelEventRead
    Errors: 404 if cycle not found
    """
    return crud.create_wheel_event(db, payload)


@router.put("/wheel-events/{event_id}", response_model=schemas.WheelEventRead)
@router.put("/wheel_events/{event_id}", response_model=schemas.WheelEventRead)
def update_wheel_event(event_id: int, payload: schemas.WheelEventCreate, db: Session = Depends(get_db)):
    """Update a wheel event by ID.

    Path: event_id
    Input: WheelEventCreate
    Returns: WheelEventRead
    Errors: 404 if not found
    """
    return crud.update_wheel_event(db, event_id, payload)


@router.delete("/wheel-events/{event_id}")
@router.delete("/wheel_events/{event_id}")
def delete_wheel_event(event_id: int, db: Session = Depends(get_db)):
    """Delete a wheel event by ID.

    Returns: { detail: string }
    Errors: 404 if not found
    """
    ok = crud.delete_wheel_event(db, event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Wheel event not found")
    return {"detail": "Wheel event deleted"}


@router.get("/wheel-metrics/{cycle_id}", response_model=schemas.WheelMetricsRead)
@router.get("/wheel_metrics/{cycle_id}", response_model=schemas.WheelMetricsRead)
def get_wheel_metrics(cycle_id: int, db: Session = Depends(get_db)):
    """Get summary wheel metrics for a cycle.

    Returns: WheelMetricsRead
    Errors: 404 if cycle not found
    """
    return crud.calculate_wheel_metrics(db, cycle_id)


# --- Lot endpoints ---
@router.get("/cycles/{cycle_id}/lots", response_model=list[schemas.LotRead])
def list_cycle_lots(cycle_id: int, status: str | None = None, covered: bool | None = None, ticker: str | None = None, db: Session = Depends(get_db)):
    """List 100-share lots for a cycle with optional filters.

    Query: status, covered, ticker
    Returns: list[LotRead]
    """
    return crud.list_lots(db, cycle_id=cycle_id, status=status, covered=covered, ticker=ticker)


@router.get("/lots/{lot_id}", response_model=schemas.LotRead)
def get_lot(lot_id: int, db: Session = Depends(get_db)):
    """Get a single lot by ID.

    Errors: 404 if not found
    """
    lot = crud.get_lot(db, lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    return lot


@router.patch("/lots/{lot_id}", response_model=schemas.LotRead)
def patch_lot(lot_id: int, payload: schemas.LotUpdate, db: Session = Depends(get_db)):
    """Patch mutable fields of a lot (status, notes, cost basis, acquisition_date).

    Errors: 404 if not found
    """
    updated = crud.update_lot(db, lot_id, schemas.LotBase(**{**(crud.get_lot(db, lot_id).__dict__ if crud.get_lot(db, lot_id) else {}), **payload.model_dump(exclude_unset=True)}))
    if not updated:
        raise HTTPException(status_code=404, detail="Lot not found")
    return updated


@router.get("/lots/{lot_id}/metrics", response_model=schemas.LotMetricsRead)
def get_lot_metrics(lot_id: int, db: Session = Depends(get_db)):
    """Compute/refresh lot metrics and return them."""
    return crud.refresh_lot_metrics(db, lot_id)


@router.post("/lots/rebuild")
def rebuild_lots(cycle_id: int, db: Session = Depends(get_db)):
    """Rebuild lots deterministically from events for the given cycle.

    Returns: { created: number }
    """
    lots = crud.rebuild_lots_for_cycle(db, cycle_id)
    return {"created": len(lots)}


class BindCallPayload(BaseModel):
    option_event_id: int


@router.post("/lots/{lot_id}/bind-call")
def bind_call(lot_id: int, payload: BindCallPayload, db: Session = Depends(get_db)):
    """Link an option SELL_CALL_OPEN event to a lot and mark it covered.

    Errors: 404 if lot not found, 400 if event is not a SELL_CALL_OPEN
    """
    lot = crud.get_lot(db, lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    evt = crud.get_wheel_event(db, payload.option_event_id)
    if not evt or evt.event_type != "SELL_CALL_OPEN":
        raise HTTPException(status_code=400, detail="Invalid option event to bind")
    crud.create_lot_link(db, schemas.LotLinkCreate(lot_id=lot_id, linked_object_type="WHEEL_EVENT", linked_object_id=evt.id, role="CALL_OPEN"))
    lot.status = "OPEN_COVERED"
    db.commit()
    crud.refresh_lot_metrics(db, lot_id)
    return {"detail": "Bound"}


@router.post("/lots/{lot_id}/unbind-call")
def unbind_call(lot_id: int, db: Session = Depends(get_db)):
    """Remove call links from a lot and mark it uncovered.

    Errors: 404 if lot not found
    """
    lot = crud.get_lot(db, lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    # delete call links
    links = crud.list_lot_links(db, lot_id)
    for l in links:
        if l.role in ("CALL_OPEN", "CALL_CLOSE"):
            crud.delete_lot_link(db, l.id)
    lot.status = "OPEN_UNCOVERED"
    db.commit()
    crud.refresh_lot_metrics(db, lot_id)
    return {"detail": "Unbound"}


@router.post("/lots/{lot_id}/bind-call-close")
def bind_call_close(lot_id: int, payload: BindCallPayload, db: Session = Depends(get_db)):
    """Bind a SELL_CALL_CLOSE event to a covered lot and mark it uncovered.

    Errors: 404 if lot not found, 400 if event is not SELL_CALL_CLOSE
    """
    lot = crud.get_lot(db, lot_id)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    evt = crud.get_wheel_event(db, payload.option_event_id)
    if not evt or evt.event_type != "SELL_CALL_CLOSE":
        raise HTTPException(status_code=400, detail="Invalid close event to bind")
    crud.create_lot_link(db, schemas.LotLinkCreate(lot_id=lot_id, linked_object_type="WHEEL_EVENT", linked_object_id=evt.id, role="CALL_CLOSE"))
    # closing coverage makes it uncovered again unless already called away
    if lot.status == "OPEN_COVERED":
        lot.status = "OPEN_UNCOVERED"
        db.commit()
    crud.refresh_lot_metrics(db, lot_id)
    return {"detail": "Bound close"}


@router.get("/lots/{lot_id}/links")
def get_lot_links(lot_id: int, db: Session = Depends(get_db)):
    """Return lot links and their linked wheel events to aid the UI.

    Returns: { links: LotLinkRead[], events: WheelEventRead[] }
    """
    links = crud.list_lot_links(db, lot_id)
    event_ids = [l.linked_object_id for l in links if l.linked_object_type == "WHEEL_EVENT"]
    events = []
    if event_ids:
        events = (
            db.query(models.WheelEvent)
            .filter(models.WheelEvent.id.in_(event_ids))
            .order_by(models.WheelEvent.trade_date.asc(), models.WheelEvent.id.asc())
            .all()
        )
    # Pydantic conversion
    return {
        "links": [schemas.LotLinkRead(id=l.id, lot_id=l.lot_id, linked_object_type=l.linked_object_type, linked_object_id=l.linked_object_id, role=l.role) for l in links],
        "events": [
            schemas.WheelEventRead(
                id=e.id,
                cycle_id=e.cycle_id,
                event_type=e.event_type,
                trade_date=e.trade_date,
                quantity_shares=e.quantity_shares,
                contracts=e.contracts,
                price=e.price,
                strike=e.strike,
                premium=e.premium,
                fees=e.fees,
                link_event_id=e.link_event_id,
                notes=e.notes,
            ) for e in events
        ]
    }


# ===== OPTIMIZED ENDPOINTS FOR PERFORMANCE =====

@router.get("/tickers/{ticker}/wheel-data")
def get_ticker_wheel_data_optimized(
    ticker: str, 
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get comprehensive wheel data for a ticker in optimized queries.
    
    This endpoint replaces multiple individual calls with a single optimized request
    that fetches cycles, events, lots, and metrics in minimal database queries.
    
    Returns:
        - cycles: List of wheel cycles for the ticker
        - events: All events across all cycles
        - lots: All lots with their events pre-loaded
        - events_by_lot: Dict mapping lot_id to list of events
        - metrics: Aggregated metrics across all cycles
    """
    try:
        data = BatchLoaderService.get_wheel_data_for_ticker(db, ticker)
        
        # Convert to API response format
        return {
            "cycles": [
                schemas.WheelCycleRead(
                    id=c.id,
                    ticker=c.ticker,
                    cycle_key=c.cycle_key,
                    started_at=c.started_at,
                    ended_at=c.ended_at,
                    status=c.status,
                    initial_stock_price=c.initial_stock_price,
                    put_strike=c.put_strike,
                    capital_at_risk=c.capital_at_risk,
                    notes=c.notes
                ) for c in data["cycles"]
            ],
            "events": [
                schemas.WheelEventRead(
                    id=e.id,
                    cycle_id=e.cycle_id,
                    event_type=e.event_type,
                    trade_date=e.trade_date,
                    quantity_shares=e.quantity_shares,
                    contracts=e.contracts,
                    price=e.price,
                    strike=e.strike,
                    premium=e.premium,
                    fees=e.fees,
                    link_event_id=e.link_event_id,
                    notes=e.notes
                ) for e in data["events"]
            ],
            "lots": [
                schemas.LotRead(
                    id=lot.id,
                    cycle_id=lot.cycle_id,
                    lot_id=lot.lot_id,
                    acquisition_method=lot.acquisition_method,
                    acquisition_date=lot.acquisition_date,
                    acquisition_price=lot.acquisition_price,
                    quantity_initial=lot.quantity_initial,
                    status=lot.status,
                    cost_basis=lot.cost_basis,
                    realized_pl=lot.realized_pl,
                    notes=lot.notes
                ) for lot in data["lots"]
            ],
            "events_by_lot": {
                str(lot_id): [
                    schemas.WheelEventRead(
                        id=e.id,
                        cycle_id=e.cycle_id,
                        event_type=e.event_type,
                        trade_date=e.trade_date,
                        quantity_shares=e.quantity_shares,
                        contracts=e.contracts,
                        price=e.price,
                        strike=e.strike,
                        premium=e.premium,
                        fees=e.fees,
                        link_event_id=e.link_event_id,
                        notes=e.notes
                    ) for e in events
                ] for lot_id, events in data["events_by_lot"].items()
            },
            "metrics": data["metrics"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to load wheel data for ticker {ticker}: {str(e)}"
        )


@router.post("/refresh-prices")
def refresh_ticker_prices(
    tickers: list[str],
    db: Session = Depends(get_db)
) -> Dict[str, Optional[float]]:
    """
    Refresh current prices for multiple tickers efficiently.
    
    This endpoint batches price fetching and database updates to minimize
    API calls and database transactions.
    
    Args:
        tickers: List of ticker symbols to refresh
        
    Returns:
        Dict mapping ticker to current price (or None if failed)
    """
    try:
        # Convert to uppercase for consistency
        tickers_upper = [t.upper() for t in tickers]
        
        # Batch refresh prices
        results = refresh_prices_batch(db, tickers_upper)
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh prices: {str(e)}"
        )


class CycleMetricsRequest(BaseModel):
    cycle_ids: list[int]


@router.post("/metrics/aggregate")
def get_aggregated_cycle_metrics(
    request: CycleMetricsRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get aggregated metrics across multiple cycles efficiently.
    
    This endpoint calculates performance metrics across multiple cycles
    without requiring individual cycle queries.
    
    Args:
        cycle_ids: List of cycle IDs to include in aggregation
        
    Returns:
        Aggregated metrics including P&L, cashflow, and performance ratios
    """
    try:
        metrics = MetricsService.aggregate_ticker_metrics(db, request.cycle_ids)
        
        if metrics is None:
            raise HTTPException(
                status_code=404,
                detail="Unable to calculate metrics for the provided cycles"
            )
            
        return metrics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate aggregated metrics: {str(e)}"
        )


@router.get("/cycles/batch")
def get_cycles_with_lots_batch(
    cycle_ids: str,  # Comma-separated list of cycle IDs
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get multiple cycles with their lots and events in a single optimized query.
    
    This endpoint is designed for dashboard views that need to display
    multiple cycles simultaneously without N+1 query problems.
    
    Args:
        cycle_ids: Comma-separated string of cycle IDs (e.g., "1,2,3")
        
    Returns:
        Cycles with lots and events grouped by cycle
    """
    try:
        # Parse cycle IDs
        try:
            cycle_id_list = [int(id.strip()) for id in cycle_ids.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid cycle_ids format. Use comma-separated integers."
            )
        
        # Get cycles
        cycles = db.query(models.WheelCycle).filter(
            models.WheelCycle.id.in_(cycle_id_list)
        ).all()
        
        if not cycles:
            return {"cycles": [], "lots_by_cycle": {}, "events_by_lot": {}}
        
        # Batch load lots and events
        lots, events_by_lot = BatchLoaderService.get_lots_with_events_optimized(
            db, cycle_id_list
        )
        
        # Group lots by cycle
        lots_by_cycle = {}
        for lot in lots:
            cycle_id = lot.cycle_id
            if cycle_id not in lots_by_cycle:
                lots_by_cycle[cycle_id] = []
            lots_by_cycle[cycle_id].append(lot)
        
        return {
            "cycles": [
                schemas.WheelCycleRead(
                    id=c.id,
                    ticker=c.ticker,
                    cycle_key=c.cycle_key,
                    started_at=c.started_at,
                    ended_at=c.ended_at,
                    status=c.status,
                    initial_stock_price=c.initial_stock_price,
                    put_strike=c.put_strike,
                    capital_at_risk=c.capital_at_risk,
                    notes=c.notes
                ) for c in cycles
            ],
            "lots_by_cycle": {
                str(cycle_id): [
                    schemas.LotRead(
                        id=lot.id,
                        cycle_id=lot.cycle_id,
                        lot_id=lot.lot_id,
                        acquisition_method=lot.acquisition_method,
                        acquisition_date=lot.acquisition_date,
                        acquisition_price=lot.acquisition_price,
                        quantity_initial=lot.quantity_initial,
                        status=lot.status,
                        cost_basis=lot.cost_basis,
                        realized_pl=lot.realized_pl,
                        notes=lot.notes
                    ) for lot in lots
                ] for cycle_id, lots in lots_by_cycle.items()
            },
            "events_by_lot": {
                str(lot_id): [
                    schemas.WheelEventRead(
                        id=e.id,
                        cycle_id=e.cycle_id,
                        event_type=e.event_type,
                        trade_date=e.trade_date,
                        quantity_shares=e.quantity_shares,
                        contracts=e.contracts,
                        price=e.price,
                        strike=e.strike,
                        premium=e.premium,
                        fees=e.fees,
                        link_event_id=e.link_event_id,
                        notes=e.notes
                    ) for e in events
                ] for lot_id, events in events_by_lot.items()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load cycles with lots: {str(e)}"
        )


# ===== ENHANCED WHEEL DETECTION ENDPOINTS =====

class WheelDetectionOptions(BaseModel):
    """Enhanced detection options for wheel strategy detection"""
    cash_balance: Optional[float] = None
    account_type: Optional[str] = None
    risk_tolerance: Optional[str] = "moderate"  # conservative, moderate, aggressive
    include_historical: Optional[bool] = False
    market_data: Optional[Dict[str, Any]] = None

class MarketContextData(BaseModel):
    """Market context for enhanced confidence scoring"""
    volatility: Optional[float] = None
    market_trend: Optional[str] = None  # bullish, bearish, neutral
    sector: Optional[str] = None
    market_cap: Optional[str] = None  # small, mid, large

class WheelDetectionRequest(BaseModel):
    """Request body for wheel detection"""
    options: Optional[WheelDetectionOptions] = None
    account_id: Optional[int] = None
    specific_tickers: Optional[List[str]] = None

class PositionForDetection(BaseModel):
    """Position data formatted for detection algorithm"""
    id: str
    symbol: str
    shares: float
    is_option: bool = False
    underlying_symbol: Optional[str] = None
    option_type: Optional[str] = None  # Call, Put
    strike_price: Optional[float] = None
    expiration_date: Optional[str] = None
    contracts: Optional[float] = None
    market_value: float
    source: str

class RiskAssessment(BaseModel):
    """Risk assessment for detected wheel strategies"""
    level: str  # low, medium, high
    factors: List[str]
    max_loss: Optional[float] = None
    assignment_risk: Optional[float] = None  # 0-100 probability

class EnhancedPosition(BaseModel):
    """Enhanced position data with detection metadata"""
    type: str  # stock, call, put
    symbol: str
    quantity: float  # Absolute quantity for display
    position: str  # long, short
    strike_price: Optional[float] = None
    expiration_date: Optional[str] = None
    days_to_expiration: Optional[int] = None
    market_value: float
    raw_quantity: Optional[float] = None  # Preserve signed quantity for logic
    source: str

class PotentialAction(BaseModel):
    """Action recommendation with priority"""
    action: str
    description: str
    priority: str  # high, medium, low

class WheelDetectionResult(BaseModel):
    """Enhanced wheel detection result"""
    ticker: str
    strategy: str  # cash_secured_put, covered_call, full_wheel, naked_stock
    confidence: str  # high, medium, low
    confidence_score: float  # 0-100 numerical score
    description: str
    cash_required: Optional[float] = None  # Required cash for CSP strategies
    cash_validated: Optional[bool] = None  # Whether cash requirements are met
    risk_assessment: RiskAssessment
    positions: List[EnhancedPosition]
    recommendations: Optional[List[str]] = None
    potential_actions: Optional[List[PotentialAction]] = None
    market_context: Optional[MarketContextData] = None

def calculate_days_to_expiration(expiration_date: str) -> int:
    """Calculate days to expiration from date string"""
    try:
        if "T" in expiration_date:
            exp_date = datetime.fromisoformat(expiration_date.replace("Z", "+00:00"))
        else:
            exp_date = datetime.fromisoformat(expiration_date)
        today = datetime.now()
        diff_time = exp_date - today
        return max(0, diff_time.days)
    except Exception:
        return 0

def calculate_confidence_score(
    strategy: str,
    positions: List[EnhancedPosition],
    cash_required: float = 0,
    cash_balance: float = 0,
    market_context: Optional[MarketContextData] = None
) -> tuple[str, float]:
    """Calculate confidence score based on multiple factors"""
    score = 50  # Base score

    # Strategy completeness
    strategy_scores = {
        'full_wheel': 30,
        'covered_call': 20,
        'cash_secured_put': 15,
        'naked_stock': 10
    }
    score += strategy_scores.get(strategy, 0)

    # Cash validation (for CSP strategies)
    if cash_required > 0:
        if cash_balance >= cash_required:
            score += 15  # Sufficient cash
        elif cash_balance >= cash_required * 0.5:
            score += 5   # Partial cash coverage
        else:
            score -= 10  # Insufficient cash

    # Days to expiration factor
    option_positions = [p for p in positions if p.days_to_expiration is not None]
    if option_positions:
        avg_days_to_exp = sum(p.days_to_expiration for p in option_positions) / len(option_positions)
        if avg_days_to_exp > 30:
            score += 10  # Good time horizon
        elif avg_days_to_exp < 7:
            score -= 15  # Close to expiration

    # Market context (if available)
    if market_context:
        if market_context.volatility and market_context.volatility > 0.3:
            score += 5  # Higher volatility = better premiums
        if market_context.market_trend == 'bullish':
            score += 5  # Bullish trend favors wheels

    # Ensure score is within bounds
    score = max(0, min(100, score))

    # Determine confidence level
    if score >= 70:
        confidence = 'high'
    elif score >= 40:
        confidence = 'medium'
    else:
        confidence = 'low'

    return confidence, score

def calculate_cash_required(short_puts: List[EnhancedPosition]) -> float:
    """Calculate cash required for CSP strategy"""
    total = 0.0
    for put in short_puts:
        if put.type == 'put' and put.position == 'short' and put.strike_price:
            contracts = abs(put.raw_quantity or 0) / 100 if put.raw_quantity else put.quantity / 100
            total += contracts * put.strike_price * 100  # 100 shares per contract
    return total

def assess_risk(
    strategy: str,
    positions: List[EnhancedPosition],
    options: Optional[WheelDetectionOptions] = None
) -> RiskAssessment:
    """Assess risk factors for a strategy"""
    factors = []
    level = "medium"
    assignment_risk = 50.0  # Default 50%

    # Check days to expiration
    short_options = [p for p in positions if p.position == 'short' and p.days_to_expiration is not None]
    if short_options:
        min_days_to_exp = min(p.days_to_expiration for p in short_options)
        if min_days_to_exp < 7:
            factors.append('Options expiring within 7 days - high assignment risk')
            assignment_risk = 80.0
            level = 'high'
        elif min_days_to_exp < 21:
            factors.append('Options expiring within 3 weeks - moderate assignment risk')
            assignment_risk = 60.0

    # Risk tolerance adjustment
    if options and options.risk_tolerance:
        if options.risk_tolerance == 'conservative':
            factors.append('Conservative risk profile - consider safer strikes')
            if level == 'medium':
                level = 'high'
        elif options.risk_tolerance == 'aggressive':
            factors.append('Aggressive risk profile - monitor positions closely')

    # Strategy-specific risk factors
    if strategy == 'cash_secured_put':
        factors.append('Assignment would result in stock ownership')
        if assignment_risk > 70:
            factors.append('High probability of assignment at current levels')
    elif strategy == 'covered_call':
        factors.append('Call assignment would result in stock sale')
    elif strategy == 'full_wheel':
        factors.append('Multiple assignment possibilities - complex management')
        if level != 'high':
            level = 'medium'

    return RiskAssessment(
        level=level,
        factors=factors,
        assignment_risk=assignment_risk
    )

def group_positions_by_ticker(positions: List[PositionForDetection]) -> Dict[str, List[PositionForDetection]]:
    """Group positions by their underlying ticker symbol"""
    grouped = {}
    for position in positions:
        ticker = position.underlying_symbol if position.is_option else position.symbol
        if ticker not in grouped:
            grouped[ticker] = []
        grouped[ticker].append(position)
    return grouped

def analyze_ticker_positions(
    ticker: str,
    positions: List[PositionForDetection],
    options: Optional[WheelDetectionOptions] = None
) -> Optional[WheelDetectionResult]:
    """Analyze positions for a specific ticker to detect wheel strategies"""
    
    stock_positions = [p for p in positions if not p.is_option]
    option_positions = [p for p in positions if p.is_option]
    call_options = [p for p in option_positions if p.option_type == 'Call']
    put_options = [p for p in option_positions if p.option_type == 'Put']

    # Calculate total stock holdings
    total_stock_shares = sum(p.shares for p in stock_positions)

    # Separate long/short options - Use signed values
    short_calls = [p for p in call_options if (p.contracts or 0) < 0]
    short_puts = [p for p in put_options if (p.contracts or 0) < 0]

    # Enhanced position formatting
    formatted_positions = []
    for p in positions:
        is_short_position = p.is_option and (p.contracts or 0) < 0 or not p.is_option and p.shares < 0
        raw_quantity = p.contracts or 0 if p.is_option else p.shares
        days_to_expiration = calculate_days_to_expiration(p.expiration_date) if p.expiration_date else None

        enhanced_pos = EnhancedPosition(
            type='call' if p.is_option and p.option_type == 'Call' else 'put' if p.is_option and p.option_type == 'Put' else 'stock',
            symbol=p.symbol,
            quantity=abs(raw_quantity),
            position='short' if is_short_position else 'long',
            strike_price=p.strike_price,
            expiration_date=p.expiration_date,
            days_to_expiration=days_to_expiration,
            market_value=p.market_value,
            raw_quantity=raw_quantity,
            source=p.source
        )
        formatted_positions.append(enhanced_pos)

    # Detection logic
    if is_full_wheel(total_stock_shares, short_calls, short_puts):
        return create_full_wheel_result(ticker, formatted_positions, short_puts, options)
    elif is_covered_call(total_stock_shares, short_calls):
        return create_covered_call_result(ticker, formatted_positions, total_stock_shares, short_calls, options)
    elif is_cash_secured_put(short_puts):
        return create_cash_secured_put_result(ticker, formatted_positions, short_puts, total_stock_shares, options)
    elif is_naked_stock(total_stock_shares, option_positions):
        if total_stock_shares >= 100:
            return create_naked_stock_result(ticker, formatted_positions, total_stock_shares, options)

    return None

def is_full_wheel(stock_shares: float, short_calls: List, short_puts: List) -> bool:
    """Detect full wheel: 100+ shares + short call + evidence of put selling"""
    return stock_shares >= 100 and len(short_calls) > 0 and len(short_puts) > 0

def is_covered_call(stock_shares: float, short_calls: List) -> bool:
    """Detect covered call: 100+ shares + short call(s)"""
    return stock_shares >= 100 and len(short_calls) > 0

def is_cash_secured_put(short_puts: List) -> bool:
    """Detect cash-secured put: short put(s)"""
    return len(short_puts) > 0

def is_naked_stock(stock_shares: float, option_positions: List) -> bool:
    """Detect naked stock: stock holdings with no options"""
    return stock_shares > 0 and len(option_positions) == 0

def create_full_wheel_result(
    ticker: str,
    positions: List[EnhancedPosition],
    short_puts: List,
    options: Optional[WheelDetectionOptions]
) -> WheelDetectionResult:
    """Create enhanced Full Wheel result"""
    cash_required = calculate_cash_required([p for p in positions if p.type == 'put' and p.position == 'short'])
    confidence, score = calculate_confidence_score(
        'full_wheel',
        positions,
        cash_required,
        options.cash_balance if options else 0,
        options.market_data if options else None
    )
    risk_assessment = assess_risk('full_wheel', positions, options)

    return WheelDetectionResult(
        ticker=ticker,
        strategy='full_wheel',
        confidence=confidence,
        confidence_score=score,
        description=f'Complete wheel strategy: {sum(p.quantity for p in positions if p.type == "stock")} shares with covered call and put-selling capability',
        cash_required=cash_required,
        cash_validated=options.cash_balance >= cash_required if options and options.cash_balance else None,
        risk_assessment=risk_assessment,
        positions=positions,
        recommendations=[
            'Monitor covered call for expiration or early assignment',
            'Consider rolling call option if needed',
            'Look for opportunities to sell additional puts if assigned'
        ],
        potential_actions=[
            PotentialAction(action='roll_call', description='Roll covered call to later expiration', priority='high'),
            PotentialAction(action='close_call', description='Buy back call option for profit', priority='medium'),
            PotentialAction(action='sell_put', description='Sell additional cash-secured puts', priority='low')
        ],
        market_context=options.market_data if options else None
    )

def create_covered_call_result(
    ticker: str,
    positions: List[EnhancedPosition],
    total_stock_shares: float,
    short_calls: List,
    options: Optional[WheelDetectionOptions]
) -> WheelDetectionResult:
    """Create enhanced Covered Call result"""
    confidence, score = calculate_confidence_score('covered_call', positions, 0, options.cash_balance if options else 0)
    risk_assessment = assess_risk('covered_call', positions, options)
    short_call_count = len([p for p in positions if p.type == 'call' and p.position == 'short'])

    return WheelDetectionResult(
        ticker=ticker,
        strategy='covered_call',
        confidence=confidence,
        confidence_score=score,
        description=f'Covered call position: {total_stock_shares} shares with {short_call_count} short call(s)',
        risk_assessment=risk_assessment,
        positions=positions,
        recommendations=[
            'Monitor for potential assignment at expiration',
            'Consider rolling call if wanting to keep shares',
            'Could evolve into full wheel by selling puts'
        ],
        potential_actions=[
            PotentialAction(action='roll_call', description='Extend call expiration', priority='high'),
            PotentialAction(action='sell_put', description='Start wheel by selling puts below current price', priority='medium')
        ],
        market_context=options.market_data if options else None
    )

def create_cash_secured_put_result(
    ticker: str,
    positions: List[EnhancedPosition],
    short_puts: List,
    total_stock_shares: float,
    options: Optional[WheelDetectionOptions]
) -> WheelDetectionResult:
    """Create enhanced Cash-Secured Put result"""
    cash_required = calculate_cash_required([p for p in positions if p.type == 'put' and p.position == 'short'])
    confidence, score = calculate_confidence_score('cash_secured_put', positions, cash_required, options.cash_balance if options else 0)
    risk_assessment = assess_risk('cash_secured_put', positions, options)
    short_put_count = len([p for p in positions if p.type == 'put' and p.position == 'short'])

    return WheelDetectionResult(
        ticker=ticker,
        strategy='cash_secured_put',
        confidence=confidence,
        confidence_score=score,
        description=f'Cash-secured put position: {short_put_count} short put(s) {f"with {total_stock_shares} existing shares" if total_stock_shares > 0 else ""}',
        cash_required=cash_required,
        cash_validated=options.cash_balance >= cash_required if options and options.cash_balance else None,
        risk_assessment=risk_assessment,
        positions=positions,
        recommendations=[
            'Prepare for potential assignment',
            'Ensure sufficient cash to purchase shares',
            'Plan covered call strategy if assigned'
        ],
        potential_actions=[
            PotentialAction(action='manage_assignment', description='Prepare for potential share assignment', priority='high'),
            PotentialAction(action='roll_put', description='Roll put to avoid assignment', priority='medium')
        ],
        market_context=options.market_data if options else None
    )

def create_naked_stock_result(
    ticker: str,
    positions: List[EnhancedPosition],
    total_stock_shares: float,
    options: Optional[WheelDetectionOptions]
) -> WheelDetectionResult:
    """Create enhanced Naked Stock result"""
    confidence, score = calculate_confidence_score('naked_stock', positions, 0, options.cash_balance if options else 0)
    risk_assessment = assess_risk('naked_stock', positions, options)

    return WheelDetectionResult(
        ticker=ticker,
        strategy='naked_stock',
        confidence=confidence,
        confidence_score=score,
        description=f'{total_stock_shares} shares ready for wheel strategy',
        risk_assessment=risk_assessment,
        positions=positions,
        recommendations=[
            'Consider selling covered calls to generate income',
            'Stock position is suitable for wheel strategy',
            'Could start with covered calls above current price'
        ],
        potential_actions=[
            PotentialAction(action='sell_call', description='Start covered call strategy', priority='high'),
            PotentialAction(action='start_wheel', description='Begin full wheel strategy', priority='medium')
        ],
        market_context=options.market_data if options else None
    )

@router.post("/detect", response_model=List[WheelDetectionResult])
async def detect_wheel_strategies(
    request: WheelDetectionRequest,
    db: Session = Depends(get_db)
):
    """
    Enhanced wheel strategy detection with unified data model integration.
    
    Analyzes positions to identify potential wheel strategies:
    1. Cash-Secured Put: Short put option only
    2. Covered Call: 100+ shares of stock + short call option  
    3. Full Wheel: 100+ shares + short call + potential assignment history
    4. Naked Stock: Stock positions suitable for wheel strategies
    
    Features:
    - Cash balance validation for CSP strategies
    - Numerical confidence scoring (0-100)
    - Risk assessment with assignment probability
    - Days to expiration calculation
    - Priority-based action recommendations
    - Market context integration
    """
    try:
        # Get positions from unified tables
        query = db.query(Position).filter(Position.is_active == True)
        
        if request.account_id:
            query = query.filter(Position.account_id == request.account_id)
            
        positions = query.all()
        
        # Convert to detection format
        detection_positions = []
        for pos in positions:
            # Skip if specific tickers requested and this isn't one of them
            ticker = pos.underlying_symbol or pos.symbol
            if request.specific_tickers and ticker.upper() not in [t.upper() for t in request.specific_tickers]:
                continue
                
            # Calculate contracts for options
            contracts = None
            if pos.asset_type == "OPTION":
                # Net contracts = long - short quantity
                contracts = pos.long_quantity - pos.short_quantity
                
            detection_pos = PositionForDetection(
                id=str(pos.id),
                symbol=pos.symbol,
                shares=pos.long_quantity - pos.short_quantity,  # Net shares
                is_option=pos.asset_type == "OPTION",
                underlying_symbol=pos.underlying_symbol,
                option_type=pos.option_type,
                strike_price=pos.strike_price,
                expiration_date=pos.expiration_date.isoformat() if pos.expiration_date else None,
                contracts=contracts,
                market_value=pos.market_value or 0.0,
                source=pos.data_source or "unknown"
            )
            detection_positions.append(detection_pos)
        
        if not detection_positions:
            return []
        
        # Group by ticker and analyze
        grouped_positions = group_positions_by_ticker(detection_positions)
        results = []
        
        for ticker, ticker_positions in grouped_positions.items():
            detection_result = analyze_ticker_positions(ticker, ticker_positions, request.options)
            if detection_result:
                results.append(detection_result)
        
        # Sort by strategy complexity and confidence score
        strategy_order = {'full_wheel': 0, 'covered_call': 1, 'cash_secured_put': 2, 'naked_stock': 3}
        results.sort(key=lambda x: (strategy_order.get(x.strategy, 4), -x.confidence_score))
        
        return results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to detect wheel strategies: {str(e)}"
        )