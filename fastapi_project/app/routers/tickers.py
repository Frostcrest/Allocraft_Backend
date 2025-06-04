from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.dependencies import require_authenticated_user, require_role
from app.database import get_db
from app import crud, schemas

router = APIRouter(prefix="/tickers", tags=["Tickers"])

@router.post("/", response_model=schemas.TickerRead)
def create_ticker(ticker: schemas.TickerCreate, db: Session = Depends(get_db)):
    """Create a new ticker by symbol (fetches from external API if needed)."""
    return crud.create_ticker(db, ticker.symbol)

@router.get("/", response_model=list[schemas.TickerRead])
def read_tickers(symbol: str = None, db: Session = Depends(get_db)):
    """
    Get all tickers, or a single ticker by symbol if provided.
    """
    if symbol:
        ticker = crud.get_ticker_by_symbol(db, symbol)
        return [ticker] if ticker else []
    return crud.get_tickers(db)

@router.get("/{ticker_id}", response_model=schemas.TickerRead)
def get_ticker_by_id(ticker_id: int, db: Session = Depends(get_db)):
    """Get a single ticker by its ID."""
    return crud.get_ticker_by_id(db, ticker_id)

@router.delete("/{ticker_id}")
def delete_ticker(ticker_id: int, db: Session = Depends(get_db)):
    """Delete a ticker by ID."""
    return crud.delete_ticker(db, ticker_id)

@router.get("/", response_model=list[schemas.StockRead])
def get_stocks(
    db: Session = Depends(get_db),
    current_user=Depends(require_authenticated_user)  # Require login
):
    return crud.get_stocks(db)

@router.delete("/{stock_id}")
def delete_stock(
    stock_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin"))  # Require admin role
):
    success = crud.delete_stock(db, stock_id)
    if not success:
        raise HTTPException(status_code=404, detail="Stock not found")
    return {"detail": "Stock deleted"}