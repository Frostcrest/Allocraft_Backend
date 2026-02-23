"""
Stocks Router

Beginner guide:
- Basic CRUD and CSV import for stock positions (legacy model).
- Some endpoints require auth or admin role; in local dev DISABLE_AUTH=1 bypasses this.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from .. import schemas, crud, models
from ..services.stocks_service import StocksService
from ..database import get_db
from fastapi.responses import StreamingResponse
import io
import csv
from ..dependencies import require_authenticated_user, require_role

router = APIRouter(prefix="/stocks", tags=["Stocks"])

@router.get("/")
def read_stocks(db: Session = Depends(get_db), refresh_prices: bool = False, skip: int = 0, limit: int = 1000):
    """Get stocks from unified Position table (shows imported Schwab data + manual entries)."""
    try:
        return StocksService.read_stocks(db, skip, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stocks: {str(e)}")

@router.get("/all-positions")
def get_all_positions(db: Session = Depends(get_db), current_user: models.User = Depends(require_authenticated_user)):
    """Get all positions from unified Position table (replaces old manual + Schwab split)."""
    try:
        return StocksService.get_all_positions(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching positions: {str(e)}")

@router.post("/", response_model=schemas.StockRead)
def create_stock(
    stock: schemas.StockCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_authenticated_user)
):
    """Add a new stock position."""
    try:
        return StocksService.create_stock(db, stock)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating stock: {str(e)}")

@router.put("/{stock_id}", response_model=schemas.StockRead)
def update_stock(stock_id: int, stock: schemas.StockCreate, db: Session = Depends(get_db)):
    """Update an existing stock position."""
    try:
        updated = StocksService.update_stock(db, stock_id, stock)
        if not updated:
            raise HTTPException(status_code=404, detail="Stock not found")
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating stock: {str(e)}")

@router.delete("/{stock_id}")
def delete_stock(
    stock_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin"))
):
    """Delete a stock position by its ID."""
    try:
        success = StocksService.delete_stock(db, stock_id)
        if not success:
            raise HTTPException(status_code=404, detail="Stock not found")
        return {"detail": "Stock deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting stock: {str(e)}")

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
async def upload_stock_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_authenticated_user)
):
    """Upload a CSV file to bulk add stock positions."""
    try:
        contents = await file.read()
        created_count = StocksService.upload_stock_csv(contents, db)
        return {"created": created_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading stock CSV: {str(e)}")