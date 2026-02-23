"""
Options Router

Beginner guide:
- Simple CRUD and CSV import for option contracts (legacy model).
- For Wheel strategies, prefer the event-based endpoints in wheels.py.

Common errors:
- 404 if updating/deleting an option that doesn't exist.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from .. import schemas, crud, models
from ..services.options_service import OptionsService
from ..database import get_db
from ..dependencies import require_authenticated_user
from fastapi.responses import StreamingResponse
import io
import csv

router = APIRouter(
    prefix="/options",
    tags=["Options"],
    dependencies=[Depends(require_authenticated_user)],
)

@router.get("/")
def read_options(
    db: Session = Depends(get_db),
    refresh_prices: bool = False,
    limit: int = Query(50, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
):
    """Get option contracts from unified Position table with parsed strike/expiry data."""
    try:
        all_options = OptionsService.read_options(db)
        total = len(all_options)
        items = all_options[offset : offset + limit]
        return {"items": items, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching options: {str(e)}")

@router.post("/", response_model=schemas.OptionRead)
def create_option(option: schemas.OptionCreate, db: Session = Depends(get_db)):
    """Add a new option contract."""
    try:
        return OptionsService.create_option(db, option)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating option: {str(e)}")

@router.put("/{option_id}", response_model=schemas.OptionRead)
def update_option(option_id: int, option: schemas.OptionCreate, db: Session = Depends(get_db)):
    """Update an existing option contract."""
    try:
        updated = OptionsService.update_option(db, option_id, option)
        if not updated:
            raise HTTPException(status_code=404, detail="Option not found")
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating option: {str(e)}")

@router.delete("/{option_id}")
def delete_option(option_id: int, db: Session = Depends(get_db)):
    """Delete an option contract by its ID."""
    try:
        success = OptionsService.delete_option(db, option_id)
        if not success:
            raise HTTPException(status_code=404, detail="Option not found")
        return {"detail": "Option deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting option: {str(e)}")

@router.get("/template")
def download_options_csv_template():
    """Download a CSV template for option contracts."""
    csv_content = (
        "ticker,option_type,strike_price,expiration_date,quantity,cost_basis,status,entry_date\n"
        "AAPL,call,150,2024-07-19,1,2.50,Open,2024-06-01\n"
        "MSFT,put,320,2024-08-16,2,3.10,Closed,2024-05-15\n"
    )
    return StreamingResponse(
        io.StringIO(csv_content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=options_template.csv"}
    )

@router.post("/upload")
async def upload_options_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a CSV file to bulk add option contracts."""
    try:
        contents = await file.read()
        created_count = OptionsService.upload_options_csv(contents, db)
        return {"created": created_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading options CSV: {str(e)}")

@router.post("/refresh-prices")
def refresh_option_prices(db: Session = Depends(get_db)):
    """Refresh current prices for all active option positions."""
    try:
        return OptionsService.refresh_option_prices(db)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to refresh option prices: {str(e)}")