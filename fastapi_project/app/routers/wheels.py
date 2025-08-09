from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app import schemas, crud, models
from app.database import get_db
from fastapi.responses import StreamingResponse
import io
import csv

router = APIRouter(prefix="/wheels", tags=["Wheels"])

@router.get("/", response_model=list[schemas.WheelStrategyRead])
def read_wheels(db: Session = Depends(get_db)):
    """Get all wheel strategies."""
    return crud.get_wheels(db)

@router.post("/", response_model=schemas.WheelStrategyRead)
def create_wheel(wheel: schemas.WheelStrategyCreate, db: Session = Depends(get_db)):
    """Add a new wheel strategy."""
    return crud.create_wheel(db, wheel)

@router.put("/{wheel_id}", response_model=schemas.WheelStrategyRead)
def update_wheel(wheel_id: int, wheel: schemas.WheelStrategyCreate, db: Session = Depends(get_db)):
    """Update an existing wheel strategy."""
    return crud.update_wheel(db, wheel_id, wheel)

@router.delete("/{wheel_id}")
def delete_wheel(wheel_id: int, db: Session = Depends(get_db)):
    """Delete a wheel strategy by its ID."""
    success = crud.delete_wheel(db, wheel_id)
    if not success:
        raise HTTPException(status_code=404, detail="Wheel strategy not found")
    return {"detail": "Wheel strategy deleted"}

@router.get("/template")
def download_wheels_csv_template():
    """Download a CSV template for wheel strategies."""
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
    """Upload a CSV file to bulk add wheel strategies."""
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


# --- Event-based Wheel endpoints ---

@router.get("/wheel-cycles", response_model=list[schemas.WheelCycleRead])
@router.get("/wheel_cycles", response_model=list[schemas.WheelCycleRead])
def list_wheel_cycles(db: Session = Depends(get_db)):
    return crud.list_wheel_cycles(db)


@router.post("/wheel-cycles", response_model=schemas.WheelCycleRead)
@router.post("/wheel_cycles", response_model=schemas.WheelCycleRead)
def create_wheel_cycle(payload: schemas.WheelCycleCreate, db: Session = Depends(get_db)):
    return crud.create_wheel_cycle(db, payload)


@router.put("/wheel-cycles/{cycle_id}", response_model=schemas.WheelCycleRead)
@router.put("/wheel_cycles/{cycle_id}", response_model=schemas.WheelCycleRead)
def update_wheel_cycle(cycle_id: int, payload: schemas.WheelCycleCreate, db: Session = Depends(get_db)):
    return crud.update_wheel_cycle(db, cycle_id, payload)


@router.delete("/wheel-cycles/{cycle_id}")
@router.delete("/wheel_cycles/{cycle_id}")
def delete_wheel_cycle(cycle_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_wheel_cycle(db, cycle_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Wheel cycle not found")
    return {"detail": "Wheel cycle deleted"}


@router.get("/wheel-events", response_model=list[schemas.WheelEventRead])
@router.get("/wheel_events", response_model=list[schemas.WheelEventRead])
def list_wheel_events(cycle_id: int | None = None, db: Session = Depends(get_db)):
    return crud.list_wheel_events(db, cycle_id)


@router.post("/wheel-events", response_model=schemas.WheelEventRead)
@router.post("/wheel_events", response_model=schemas.WheelEventRead)
def create_wheel_event(payload: schemas.WheelEventCreate, db: Session = Depends(get_db)):
    return crud.create_wheel_event(db, payload)


@router.put("/wheel-events/{event_id}", response_model=schemas.WheelEventRead)
@router.put("/wheel_events/{event_id}", response_model=schemas.WheelEventRead)
def update_wheel_event(event_id: int, payload: schemas.WheelEventCreate, db: Session = Depends(get_db)):
    return crud.update_wheel_event(db, event_id, payload)


@router.delete("/wheel-events/{event_id}")
@router.delete("/wheel_events/{event_id}")
def delete_wheel_event(event_id: int, db: Session = Depends(get_db)):
    ok = crud.delete_wheel_event(db, event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Wheel event not found")
    return {"detail": "Wheel event deleted"}


@router.get("/wheel-metrics/{cycle_id}", response_model=schemas.WheelMetricsRead)
@router.get("/wheel_metrics/{cycle_id}", response_model=schemas.WheelMetricsRead)
def get_wheel_metrics(cycle_id: int, db: Session = Depends(get_db)):
    return crud.calculate_wheel_metrics(db, cycle_id)