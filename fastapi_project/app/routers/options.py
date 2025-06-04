from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app import schemas, crud, models
from app.database import get_db
from fastapi.responses import StreamingResponse
import io
import csv

router = APIRouter(prefix="/options", tags=["Options"])

@router.get("/", response_model=list[schemas.OptionRead])
def read_options(db: Session = Depends(get_db)):
    """Get all option contracts."""
    return crud.get_options(db)

@router.post("/", response_model=schemas.OptionRead)
def create_option(option: schemas.OptionCreate, db: Session = Depends(get_db)):
    """Add a new option contract."""
    return crud.create_option(db, option)

@router.put("/{option_id}", response_model=schemas.OptionRead)
def update_option(option_id: int, option: schemas.OptionCreate, db: Session = Depends(get_db)):
    """Update an existing option contract."""
    return crud.update_option(db, option_id, option)

@router.delete("/{option_id}")
def delete_option(option_id: int, db: Session = Depends(get_db)):
    """Delete an option contract by its ID."""
    success = crud.delete_option(db, option_id)
    if not success:
        raise HTTPException(status_code=404, detail="Option not found")
    return {"detail": "Option deleted"}

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
    contents = await file.read()
    decoded = contents.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)
    created = []
    for row in reader:
        try:
            db_option = models.Option(
                ticker=row["ticker"].strip().upper(),
                option_type=row["option_type"].strip().capitalize(),
                strike_price=float(row["strike_price"]),
                expiry_date=row["expiration_date"],
                contracts=float(row["quantity"]),
                cost_basis=float(row["cost_basis"]),
                market_price_per_contract=None,
                status=row.get("status", "Open"),
                current_price=None,
            )
            db.add(db_option)
            created.append(db_option)
        except Exception:
            continue
    db.commit()
    return {"created": len(created)}