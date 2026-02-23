"""
Tickers Router

Beginner guide:
- Create and query ticker metadata. Creation may hit external APIs.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import schemas, crud
from ..services.tickers_service import TickersService
from ..database import get_db
from ..dependencies import require_authenticated_user

router = APIRouter(
    prefix="/tickers",
    tags=["Tickers"],
    dependencies=[Depends(require_authenticated_user)],
)

@router.post("/", response_model=schemas.TickerRead)
def create_ticker(ticker: schemas.TickerCreate, db: Session = Depends(get_db)):
    """Create a new ticker by symbol (fetches from external API if needed)."""
    try:
        return TickersService.create_ticker(db, ticker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create ticker: {str(e)}")

@router.get("/", response_model=list[schemas.TickerRead])
def read_tickers(symbol: str = None, db: Session = Depends(get_db)):
    """
    Get all tickers, or a single ticker by symbol if provided.
    """
    try:
        return TickersService.read_tickers(db, symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read tickers: {str(e)}")

@router.get("/{ticker_id}", response_model=schemas.TickerRead)
def get_ticker_by_id(ticker_id: int, db: Session = Depends(get_db)):
    """Get a single ticker by its ID."""
    try:
        ticker = TickersService.get_ticker_by_id(db, ticker_id)
        if not ticker:
            raise HTTPException(status_code=404, detail="Ticker not found")
        return ticker
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ticker: {str(e)}")

@router.delete("/{ticker_id}")
def delete_ticker(ticker_id: int, db: Session = Depends(get_db)):
    """Delete a ticker by ID."""
    try:
        success = TickersService.delete_ticker(db, ticker_id)
        if not success:
            raise HTTPException(status_code=404, detail="Ticker not found")
        return {"detail": "Ticker deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete ticker: {str(e)}")