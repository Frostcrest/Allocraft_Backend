"""
Unified Import/Export Router - Source Agnostic

Handles imports from any brokerage into unified tables.
Replaces schwab.py with source-agnostic approach.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from datetime import datetime, UTC
import json
import logging

from app.database import get_db
from app.dependencies import require_role
from app.models_unified import Account, Position
from app.models import SchwabAccount, SchwabPosition
from app.utils.option_parser import parse_option_symbol
from app.services.portfolio_service import PortfolioService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/import/positions")
async def import_positions(
    import_data: dict,
    db: Session = Depends(get_db)
):
    """
    Import positions from any brokerage export into unified tables.
    Supports Schwab, future Fidelity/TD Ameritrade, and manual CSV imports.
    No authentication required - development data seeding.
    """
    try:
        result = PortfolioService.import_positions(import_data, db)
        return result
    except ValueError as e:
        logger.error(f"Import error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected import error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to import positions")


@router.get("/positions")
async def get_positions(
    account_id: int = None,
    asset_type: str = None,
    db: Session = Depends(get_db)
):
    """Get positions from unified tables with optional filtering"""
    try:
        return PortfolioService.get_positions(db, account_id, asset_type)
    except ValueError as e:
        logger.error(f"Position query error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected position query error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get positions")


@router.post("/sync/from-schwab-tables")
@router.post("/sync/from-schwab-tables")
def sync_from_schwab_tables(
    deactivate_missing: bool = True,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin"))
):
    """Bridge existing Schwab tables into unified Account/Position."""
    try:
        return PortfolioService.sync_from_schwab_tables(db, deactivate_missing)
    except Exception as e:
        logger.error(f"Error during Schwab bridge sync: {e}")
        raise HTTPException(status_code=500, detail=f"Bridge sync failed: {str(e)}")


@router.get("/positions/stocks")
async def get_stock_positions(db: Session = Depends(get_db)):
    """Get only stock positions (EQUITY) - legacy compatibility"""
    return PortfolioService.get_stock_positions(db)

@router.get("/positions/options")
async def get_option_positions(db: Session = Depends(get_db)):
    """Get only option positions - legacy compatibility"""
    return PortfolioService.get_option_positions(db)


@router.post("/sync/schwab")
async def sync_schwab_positions(
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Future endpoint: Sync live Schwab data into unified tables
    
    This will replace the current schwab sync functionality
    but write directly to Account/Position tables with data_source="schwab_api"
    """
    # TODO: Implement live Schwab API sync
    # This would call the same Schwab API but write to unified tables
    return {
        "message": "Live Schwab sync not yet implemented",
        "note": "Will sync directly to unified Account/Position tables when ready",
        "data_source": "schwab_api"
    }


@router.get("/export/positions")
async def export_positions(db: Session = Depends(get_db)):
    """
    Export all positions from unified tables
    
    Same format as current export but from unified data source
    """
    try:
        return PortfolioService.export_positions(db)
    except Exception as e:
        logger.error(f"Error exporting positions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export positions: {str(e)}")
