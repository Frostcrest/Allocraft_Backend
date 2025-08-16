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
from ..database import get_db
from fastapi.responses import StreamingResponse
import io
import csv

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