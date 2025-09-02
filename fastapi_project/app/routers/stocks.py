"""
Stocks Router

Beginner guide:
- Basic CRUD and CSV import for stock positions (legacy model).
- Some endpoints require auth or admin role; in local dev DISABLE_AUTH=1 bypasses this.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from .. import schemas, crud, models
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
        # Import unified models
        from ..models_unified import Position
        
        # Get equity positions from unified table - FAST query
        equity_positions = db.query(Position).filter(
            Position.asset_type.in_(["EQUITY", "COLLECTIVE_INVESTMENT"]),
            Position.is_active == True
        ).offset(skip).limit(limit).all()
        
        # Convert to simple dict format - NO COMPLEX MATH
        stocks = []
        
        for pos in equity_positions:
            net_quantity = (pos.long_quantity or 0) - (pos.short_quantity or 0)
            
            # Simple dict - no expensive calculations
            stock_data = {
                "id": pos.id,
                "ticker": pos.symbol,
                "shares": net_quantity,
                "cost_basis": pos.average_price or 0.0,
                "market_price": pos.current_price or 0.0,
                "status": pos.status or "Open",
                "current_price": pos.current_price or 0.0,
                "entry_date": pos.entry_date,
                "price_last_updated": None
            }
            stocks.append(stock_data)
        
        return stocks
        
    except Exception as e:
        print(f"Unified table error, falling back to legacy: {e}")
        # Return empty list instead of falling back to avoid more complexity
        return []

@router.get("/all-positions")
def get_all_positions(db: Session = Depends(get_db), current_user: models.User = Depends(require_authenticated_user)):
    """Get all positions from unified Position table (replaces old manual + Schwab split)."""
    try:
        # Import unified models
        from ..models_unified import Position, Account
        
        positions = []
        
        # Get all positions from unified table
        all_positions = db.query(Position).filter(Position.is_active == True).all()
        accounts = {acc.id: acc for acc in db.query(Account).all()}
        
        for pos in all_positions:
            account = accounts.get(pos.account_id)
            
            # Calculate net quantity (long - short)
            net_quantity = (pos.long_quantity or 0) - (pos.short_quantity or 0)
            
            position_data = {
                "id": f"unified_{pos.id}",
                "symbol": pos.symbol,
                "shares": abs(net_quantity) if pos.asset_type in ["EQUITY", "COLLECTIVE_INVESTMENT"] else 0,
                "costBasis": pos.average_price or 0,
                "marketPrice": (pos.market_value or 0) / abs(net_quantity) if net_quantity != 0 else 0,
                "marketValue": pos.market_value or 0,
                "profitLoss": pos.current_day_profit_loss or 0,
                "source": pos.data_source or "unknown",
                "accountType": account.account_type if account else "Unknown",
                "accountNumber": account.account_number if account else "Unknown",
                "brokerage": account.brokerage if account else "Unknown",
                "isOption": pos.asset_type == "OPTION",
                "isShort": net_quantity < 0,
                "assetType": pos.asset_type,
                "status": pos.status
            }
            
            # Add option-specific fields
            if pos.asset_type == "OPTION":
                position_data.update({
                    "underlyingSymbol": pos.underlying_symbol,
                    "optionType": pos.option_type,
                    "strikePrice": pos.strike_price,
                    "expirationDate": pos.expiration_date.isoformat() if pos.expiration_date else None,
                    "contracts": abs(net_quantity)
                })
            
            positions.append(position_data)
        
        return {
            "positions": positions,
            "summary": {
                "total_positions": len(positions),
                "manual_positions": len([p for p in positions if p["source"] == "manual"]),
                "schwab_positions": len([p for p in positions if "schwab" in p["source"]]),
                "accounts": len(accounts),
                "equity_positions": len([p for p in positions if p["assetType"] in ["EQUITY", "COLLECTIVE_INVESTMENT"]]),
                "option_positions": len([p for p in positions if p["assetType"] == "OPTION"]),
                "total_market_value": sum(p["marketValue"] for p in positions),
                "equity_positions": len([p for p in positions if not p["isOption"]]),
                "option_positions": len([p for p in positions if p["isOption"]])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching positions: {str(e)}")

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
async def upload_stock_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_authenticated_user)  # Require auth in non-dev
):
    """Upload a CSV file to bulk add stock positions.

    Tolerates common header variants from spreadsheets:
    - "Ticker" -> ticker
    - "Shares" -> shares
    - "Basis" (per-share) -> cost_basis
    - ignores summary rows like "Total"
    """
    contents = await file.read()
    decoded = contents.decode("utf-8", errors="ignore").splitlines()
    reader = csv.DictReader(decoded)
    created = []
    for raw_row in reader:
        try:
            # Normalize header keys and strip values
            row = { (k or "").strip().lower(): (v or "").strip() for k, v in raw_row.items() }

            ticker = row.get("ticker")
            if not ticker:
                # Some exports might use a blank ticker for totals
                continue
            if ticker.lower() == "total":
                # Skip summary rows
                continue

            shares_str = row.get("shares")
            cost_basis_str = row.get("cost_basis") or row.get("basis") or row.get("avg_cost") or row.get("average_cost")
            # Basic required fields
            if not shares_str or not cost_basis_str:
                continue

            shares = float(shares_str)
            cost_basis = float(cost_basis_str)

            db_stock = models.Stock(
                ticker=ticker.upper(),
                shares=shares,
                cost_basis=cost_basis,
                market_price=None,
                status=row.get("status") or "Open",
                entry_date=row.get("entry_date") or row.get("date") or None,
                current_price=None,
                price_last_updated=None,
            )
            db.add(db_stock)
            created.append(db_stock)
        except Exception:
            # Ignore bad rows; continue importing others
            continue
    db.commit()
    return {"created": len(created)}