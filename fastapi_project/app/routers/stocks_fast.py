"""
Ultra-Fast Stocks Endpoint - No Schema Validation, Pure Speed
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models_unified import Position

router = APIRouter(prefix="/stocks-fast", tags=["stocks-fast"])

@router.get("/")
async def get_stocks_lightning_fast(db: Session = Depends(get_db)):
    """
    Ultra-fast stocks endpoint - returns raw data in milliseconds
    """
    try:
        # Get only EQUITY positions (stocks) with minimal fields
        positions = db.query(
            Position.id,
            Position.symbol,
            Position.long_quantity,
            Position.market_value,
            Position.average_price,
            Position.status,
            Position.data_source
        ).filter(
            Position.asset_type == "EQUITY"
        ).all()
        
        # Return raw data - no schema validation, no complex processing
        result = []
        for pos in positions:
            result.append({
                "id": pos.id,
                "ticker": pos.symbol,
                "shares": pos.long_quantity,
                "market_value": pos.market_value,
                "cost_basis": pos.average_price,
                "status": pos.status,
                "data_source": pos.data_source
            })
        
        return result
        
    except Exception as e:
        return {"error": str(e)}

@router.get("/count")
async def get_stock_count(db: Session = Depends(get_db)):
    """Just count stocks - should be instant"""
    try:
        count = db.query(Position).filter(Position.asset_type == "EQUITY").count()
        return {"stock_count": count}
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug")
async def debug_positions(db: Session = Depends(get_db)):
    """Debug what we have in the database"""
    try:
        # Count by asset type
        equity_count = db.query(Position).filter(Position.asset_type == "EQUITY").count()
        option_count = db.query(Position).filter(Position.asset_type == "OPTION").count()
        total_count = db.query(Position).count()
        
        # Get first few symbols
        sample_positions = db.query(Position.symbol, Position.asset_type).limit(5).all()
        
        return {
            "total_positions": total_count,
            "equity_count": equity_count,
            "option_count": option_count,
            "sample_symbols": [{"symbol": p.symbol, "type": p.asset_type} for p in sample_positions]
        }
    except Exception as e:
        return {"error": str(e)}
