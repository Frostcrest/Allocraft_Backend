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
        "wheel_id,ticker,trade_type,trade_date,strike_price,premium_received,status\n"
        "AAPL-W1,AAPL,Sell Put,2024-07-19,150,2.50,Open\n"
        "MSFT-W1,MSFT,Sell Call,2024-08-16,320,3.10,Closed\n"
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
                trade_type=row.get("trade_type", "Sell Put"),
                trade_date=row.get("trade_date"),
                strike_price=float(row["strike_price"]) if row.get("strike_price") else None,
                premium_received=float(row["premium_received"]) if row.get("premium_received") else None,
                status=row.get("status", "Active"),
            )
            db.add(db_wheel)
            created.append(db_wheel)
        except Exception:
            continue
    db.commit()
    return {"created": len(created)}