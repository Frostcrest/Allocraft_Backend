from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app import schemas, crud, models
from app.database import get_db
from fastapi.responses import StreamingResponse
import io
import csv
from app.dependencies import require_authenticated_user, require_role

router = APIRouter(prefix="/stocks", tags=["Stocks"])

@router.get("/", response_model=list[schemas.StockRead])
def read_stocks(db: Session = Depends(get_db), refresh_prices: bool = False):
    """Get all stocks. Optionally refresh prices."""
    return crud.get_stocks(db, refresh_prices=refresh_prices)

@router.post("/", response_model=schemas.StockRead)
def create_stock(
    stock: schemas.StockCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_authenticated_user)  # <-- Require login
):
    """Add a new stock position."""
    return crud.create_stock(db, stock)

@router.put("/{stock_id}", response_model=schemas.StockRead)
def update_stock(stock_id: int, stock: schemas.StockCreate, db: Session = Depends(get_db)):
    """Update an existing stock position."""
    return crud.update_stock(db, stock_id, stock)

@router.delete("/{stock_id}")
def delete_stock(
    stock_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin"))  # <-- Require admin role
):
    """Delete a stock position by its ID."""
    success = crud.delete_stock(db, stock_id)
    if not success:
        raise HTTPException(status_code=404, detail="Stock not found")
    return {"detail": "Stock deleted"}

@router.get("/template")
def download_stock_csv_template():
    """Download a CSV template for stock positions."""
    csv_content = "ticker,shares,cost_basis,status,entry_date\nAAPL,10,150.00,Open,2024-06-01\nMSFT,5,320.50,Sold,2024-05-15\n"
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=stock_template.csv"}
    )

@router.post("/upload")
async def upload_stock_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a CSV file to bulk add stock positions."""
    contents = await file.read()
    decoded = contents.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)
    created = []
    for row in reader:
        try:
            db_stock = models.Stock(
                ticker=row["ticker"].strip().upper(),
                shares=float(row["shares"]),
                cost_basis=float(row["cost_basis"]),
                market_price=None,
                status=row.get("status", "Open"),
                entry_date=row.get("entry_date") or None,
                current_price=None,
                price_last_updated=None,
            )
            db.add(db_stock)
            created.append(db_stock)
        except Exception:
            continue
    db.commit()
    return {"created": len(created)}