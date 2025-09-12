"""
Optimized Portfolio Import with Progress Tracking

Fast, efficient import with real-time progress updates.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, UTC
import json
import logging
import time

from app.database import get_db
from app.models_unified import Account, Position

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/import/positions")
async def import_positions_optimized(
    import_data: dict,
    db: Session = Depends(get_db)
):
    """
    Optimized position import with progress tracking.
    Uses bulk operations for speed.
    """
    start_time = time.time()
    
    try:
        logger.info("=== STARTING OPTIMIZED IMPORT ===")
        
        # Validate input
        if "accounts" not in import_data or "export_info" not in import_data:
            raise HTTPException(status_code=400, detail="Invalid import data format")
        
        account_count = len(import_data['accounts'])
        total_positions = sum(len(acc.get("positions", [])) for acc in import_data["accounts"])
        
        logger.info(f"📊 Import Summary: {account_count} accounts, {total_positions} positions")
        
        # Step 1: Clear existing data (fast bulk delete)
        logger.info("🗑️  Clearing existing data...")
        clear_start = time.time()
        
        db.execute(text("DELETE FROM positions"))
        db.execute(text("DELETE FROM accounts"))
        db.commit()
        
        clear_time = time.time() - clear_start
        logger.info(f"✅ Cleared in {clear_time:.2f}s")
        
        # Step 2: Prepare bulk data
        logger.info("📦 Preparing bulk insert data...")
        prep_start = time.time()
        
        accounts_to_insert = []
        positions_to_insert = []
        
        for i, account_data in enumerate(import_data["accounts"]):
            account_num = account_data["account_number"]
            logger.info(f"📋 Processing account {i+1}/{account_count}: {account_num}")
            
            # Prepare account data
            account_dict = {
                "account_number": account_num,
                "account_type": account_data.get("account_type", "UNKNOWN"),
                "brokerage": "schwab",
                "hash_value": account_data.get("hash_value"),
                "is_day_trader": account_data.get("is_day_trader", False),
                "cash_balance": account_data.get("cash_balance", 0.0),
                "buying_power": account_data.get("buying_power", 0.0),
                "total_value": account_data.get("total_value", 0.0),
                "day_trading_buying_power": account_data.get("day_trading_buying_power", 0.0),
                "last_synced": datetime.now(UTC),
                "is_active": True,
                "created_at": datetime.now(UTC)
            }
            accounts_to_insert.append(account_dict)
            
            # Prepare positions (we'll need to add account_id after account insert)
            positions = account_data.get("positions", [])
            logger.info(f"  📈 Processing {len(positions)} positions...")
            
            for j, pos_data in enumerate(positions):
                if j % 5 == 0 and j > 0:  # Progress every 5 positions
                    logger.info(f"    ⏳ Position {j}/{len(positions)}")
                
                # Fast underlying symbol extraction
                underlying_symbol = pos_data.get("underlying_symbol")
                if not underlying_symbol:
                    symbol = pos_data["symbol"]
                    if pos_data.get("asset_type") == "OPTION" and " " in symbol:
                        underlying_symbol = symbol.split()[0]
                    else:
                        underlying_symbol = symbol
                
                position_dict = {
                    # account_id will be set after account insert
                    "symbol": pos_data["symbol"],
                    "underlying_symbol": underlying_symbol,
                    "asset_type": pos_data.get("asset_type", "UNKNOWN"),
                    "instrument_cusip": pos_data.get("instrument_cusip"),
                    "option_type": pos_data.get("option_type"),
                    "strike_price": pos_data.get("strike_price"),
                    "long_quantity": pos_data.get("long_quantity", 0.0),
                    "short_quantity": pos_data.get("short_quantity", 0.0),
                    "settled_long_quantity": pos_data.get("settled_long_quantity", 0.0),
                    "settled_short_quantity": pos_data.get("settled_short_quantity", 0.0),
                    "market_value": pos_data.get("market_value", 0.0),
                    "average_price": pos_data.get("average_price", 0.0),
                    "average_long_price": pos_data.get("average_long_price", 0.0),
                    "average_short_price": pos_data.get("average_short_price", 0.0),
                    "current_day_profit_loss": pos_data.get("day_change", 0.0),
                    "current_day_profit_loss_percentage": pos_data.get("day_change_percent", 0.0),
                    "long_open_profit_loss": pos_data.get("long_open_profit_loss", 0.0),
                    "short_open_profit_loss": pos_data.get("short_open_profit_loss", 0.0),
                    "status": "Open" if pos_data.get("is_active", True) else "Closed",
                    "is_active": pos_data.get("is_active", True),
                    "last_updated": datetime.now(UTC),
                    "created_at": datetime.now(UTC),
                    "data_source": "schwab_import",
                    # Skip complex fields that cause slowdowns
                    "raw_data": None,  # Skip JSON serialization for speed
                    "expiration_date": None  # Handle later if needed
                }
                
                positions_to_insert.append((i, position_dict))  # Track which account
        
        prep_time = time.time() - prep_start
        logger.info(f"✅ Data prepared in {prep_time:.2f}s")
        
        # Step 3: Bulk insert accounts
        logger.info("💾 Bulk inserting accounts...")
        insert_start = time.time()
        
        db.bulk_insert_mappings(Account, accounts_to_insert)
        db.commit()
        
        # Get inserted account IDs
        inserted_accounts = db.query(Account).order_by(Account.id).all()
        account_id_map = {i: acc.id for i, acc in enumerate(inserted_accounts)}
        
        accounts_time = time.time() - insert_start
        logger.info(f"✅ {len(inserted_accounts)} accounts inserted in {accounts_time:.2f}s")
        
        # Step 4: Bulk insert positions
        logger.info("💾 Bulk inserting positions...")
        positions_start = time.time()
        
        # Add account IDs to position data
        final_positions = []
        for account_index, pos_dict in positions_to_insert:
            pos_dict["account_id"] = account_id_map[account_index]
            final_positions.append(pos_dict)
        
        # Bulk insert in chunks for better memory usage
        chunk_size = 100
        total_chunks = (len(final_positions) + chunk_size - 1) // chunk_size
        
        for i in range(0, len(final_positions), chunk_size):
            chunk = final_positions[i:i + chunk_size]
            chunk_num = (i // chunk_size) + 1
            logger.info(f"📦 Inserting chunk {chunk_num}/{total_chunks} ({len(chunk)} positions)")
            
            db.bulk_insert_mappings(Position, chunk)
        
        db.commit()
        
        positions_time = time.time() - positions_start
        total_time = time.time() - start_time
        
        logger.info(f"✅ {len(final_positions)} positions inserted in {positions_time:.2f}s")
        logger.info(f"🎉 IMPORT COMPLETE in {total_time:.2f}s total")
        
        # Final verification
        final_account_count = db.query(Account).count()
        final_position_count = db.query(Position).count()
        
        result = {
            "success": True,
            "message": "Optimized import completed successfully",
            "performance": {
                "total_time_seconds": round(total_time, 2),
                "clear_time_seconds": round(clear_time, 2),
                "prep_time_seconds": round(prep_time, 2),
                "accounts_time_seconds": round(accounts_time, 2),
                "positions_time_seconds": round(positions_time, 2),
                "positions_per_second": round(len(final_positions) / positions_time, 1)
            },
            "data": {
                "accounts_created": final_account_count,
                "positions_created": final_position_count,
                "import_timestamp": datetime.now(UTC).isoformat(),
                "data_source": "schwab_import"
            },
            "source_export": import_data["export_info"]
        }
        
        logger.info(f"📊 Final counts: {final_account_count} accounts, {final_position_count} positions")
        
        return result
        
    except Exception as e:
        db.rollback()
        total_time = time.time() - start_time
        logger.error(f"❌ Import failed after {total_time:.2f}s: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/import/status")
async def get_import_status(db: Session = Depends(get_db)):
    """Quick status check of unified tables"""
    try:
        account_count = db.query(Account).count()
        position_count = db.query(Position).count()
        
        latest_account = db.query(Account).order_by(Account.last_synced.desc()).first()
        
        return {
            "accounts": account_count,
            "positions": position_count,
            "latest_sync": latest_account.last_synced.isoformat() if latest_account and latest_account.last_synced else None,
            "status": "ready" if account_count > 0 else "empty"
        }
    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/summary")
async def get_positions_summary(db: Session = Depends(get_db)):
    """Fast summary without loading all position data"""
    try:
        # Use SQL aggregation for speed
        result = db.execute(text("""
            SELECT 
                asset_type,
                COUNT(*) as count,
                SUM(market_value) as total_value,
                SUM(long_quantity) as total_long_qty,
                SUM(short_quantity) as total_short_qty
            FROM positions 
            WHERE is_active = 1
            GROUP BY asset_type
            ORDER BY total_value DESC
        """)).fetchall()
        
        summary = []
        for row in result:
            summary.append({
                "asset_type": row[0],
                "count": row[1],
                "total_value": float(row[2]) if row[2] else 0.0,
                "total_long_quantity": float(row[3]) if row[3] else 0.0,
                "total_short_quantity": float(row[4]) if row[4] else 0.0
            })
        
        return {
            "summary": summary,
            "total_positions": sum(s["count"] for s in summary),
            "total_portfolio_value": sum(s["total_value"] for s in summary)
        }
        
    except Exception as e:
        logger.error(f"Error getting summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
