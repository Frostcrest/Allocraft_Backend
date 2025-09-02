"""
Options Router

Beginner guide:
- Simple CRUD and CSV import for option contracts (legacy model).
- For Wheel strategies, prefer the event-based endpoints in wheels.py.

Common errors:
- 404 if updating/deleting an option that doesn't exist.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from .. import schemas, crud, models
from ..database import get_db
from fastapi.responses import StreamingResponse
import io
import csv

router = APIRouter(prefix="/options", tags=["Options"])

@router.get("/")
def read_options(db: Session = Depends(get_db), refresh_prices: bool = False):
    """Get all option contracts from unified Position table with parsed strike/expiry data."""
    try:
        # Import unified models and parser
        from ..models_unified import Position
        from ..utils.option_parser import parse_option_symbol
        
        # Get option positions from unified table - FAST query
        option_positions = db.query(Position).filter(
            Position.asset_type == "OPTION",
            Position.is_active == True
        ).all()
        
        # Convert to simple dict format that the UI expects
        options = []
        
        for pos in option_positions:
            # Calculate net contracts (long - short)
            net_contracts = (pos.long_quantity or 0) - (pos.short_quantity or 0)
            
            # Parse option symbol to extract strike price and expiry
            parsed = parse_option_symbol(pos.symbol)
            
            if parsed:
                # Use parsed data
                ticker = parsed['ticker']
                option_type = parsed['option_type']
                strike_price = parsed['strike_price']
                expiry_date = parsed['expiry_date']
            else:
                # Fallback to basic parsing
                symbol_parts = pos.symbol.split()
                ticker = symbol_parts[0] if len(symbol_parts) > 0 else pos.underlying_symbol or ""
                option_type = pos.option_type or ("Put" if "P" in pos.symbol else "Call")
                strike_price = pos.strike_price or 0.0
                expiry_date = pos.expiration_date.strftime("%Y-%m-%d") if pos.expiration_date else ""
            
            # Create option data with parsed information
            option_data = {
                "id": pos.id,
                "ticker": ticker,
                "option_type": option_type,
                "strike_price": strike_price,
                "expiry_date": expiry_date,
                "contracts": abs(net_contracts),  # Always show positive for UI
                "cost_basis": pos.average_price or 0.0,
                "market_price_per_contract": pos.current_price or 0.0,
                "status": pos.status or "Open",
                "current_price": pos.current_price or 0.0,
                "price_last_updated": pos.price_last_updated.isoformat() if pos.price_last_updated else None
            }
            options.append(option_data)
        
        return options
        
    except Exception as e:
        print(f"Unified options table error: {e}")
        # Return empty list instead of falling back to avoid complexity
        return []

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

@router.post("/refresh-prices")
def refresh_option_prices(db: Session = Depends(get_db)):
    """Refresh current prices for all active option positions."""
    try:
        # Import unified models and price service
        from ..models_unified import Position
        from ..services.price_service import fetch_option_contract_price
        from ..utils.option_parser import parse_option_symbol
        from datetime import datetime, UTC
        
        # Get all active option positions
        option_positions = db.query(Position).filter(
            Position.asset_type == "OPTION",
            Position.is_active == True
        ).all()
        
        if not option_positions:
            return {"updated": 0, "failed": 0, "message": "No active option positions found"}
        
        updated_count = 0
        failed_count = 0
        failed_symbols = []
        
        # Process each option position
        for position in option_positions:
            try:
                # Parse the option symbol to get required parameters
                parsed = parse_option_symbol(position.symbol)
                
                if not parsed:
                    failed_count += 1
                    failed_symbols.append(f"{position.symbol}: Could not parse symbol")
                    continue
                
                # Extract required parameters
                ticker = parsed['ticker']
                expiry_date = parsed['expiry_date'] 
                option_type = parsed['option_type']
                strike_price = parsed['strike_price']
                
                # Fetch current option price
                current_price = fetch_option_contract_price(
                    ticker=ticker,
                    expiry_date=expiry_date,
                    option_type=option_type,
                    strike_price=strike_price
                )
                
                if current_price is not None:
                    # Update the position with current price
                    position.current_price = current_price
                    position.price_last_updated = datetime.now(UTC)
                    updated_count += 1
                else:
                    failed_count += 1
                    failed_symbols.append(f"{position.symbol}: No price data available")
                    
            except Exception as e:
                failed_count += 1
                failed_symbols.append(f"{position.symbol}: {str(e)}")
                continue
        
        # Commit all updates
        db.commit()
        
        return {
            "updated": updated_count,
            "failed": failed_count,
            "total_positions": len(option_positions),
            "failed_symbols": failed_symbols[:10] if failed_symbols else [],  # Limit to first 10 for brevity
            "message": f"Successfully updated {updated_count} of {len(option_positions)} option positions"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh option prices: {str(e)}"
        )