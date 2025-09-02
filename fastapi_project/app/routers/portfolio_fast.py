"""
Fast Portfolio Import with Progress Tracking
Optimized for speed and transparency
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models_unified import Account, Position
from datetime import datetime
import logging

router = APIRouter(prefix="/portfolio", tags=["portfolio"])
logger = logging.getLogger(__name__)

@router.post("/import-fast")
async def import_positions_fast(import_data: dict, db: Session = Depends(get_db)):
    """
    Fast import with progress tracking - optimized for large datasets
    """
    try:
        print("🚀 Starting fast import...")
        
        # Validate input
        if "accounts" not in import_data:
            raise HTTPException(status_code=400, detail="Missing 'accounts' in import data")
        
        accounts_data = import_data["accounts"]
        print(f"📊 Found {len(accounts_data)} accounts to import")
        
        # Clear existing data first (fast operation)
        print("🧹 Clearing existing unified data...")
        db.query(Position).delete()
        db.query(Account).delete()
        db.commit()
        print("✅ Existing data cleared")
        
        total_positions = 0
        
        # Process each account
        for i, account_data in enumerate(accounts_data):
            print(f"📁 Processing account {i+1}/{len(accounts_data)}: {account_data.get('account_number', 'Unknown')}")
            
            # Create account (simple, fast)
            account = Account(
                account_number=account_data["account_number"],
                account_type=account_data.get("account_type", ""),
                brokerage="schwab",
                total_value=account_data.get("total_value", 0.0),
                cash_balance=account_data.get("cash_balance", 0.0),
                buying_power=account_data.get("buying_power", 0.0),
                last_synced=datetime.utcnow()
            )
            
            db.add(account)
            db.flush()  # Get ID immediately
            print(f"✅ Account created with ID: {account.id}")
            
            # Prepare positions in batches (much faster)
            positions_data = account_data.get("positions", [])
            print(f"📈 Processing {len(positions_data)} positions...")
            
            positions_to_add = []
            
            for j, pos_data in enumerate(positions_data):
                # Show progress every 5 positions
                if j % 5 == 0:
                    print(f"  📊 Processing position {j+1}/{len(positions_data)}: {pos_data.get('symbol', 'Unknown')}")
                
                # Create position object (minimal processing)
                position = Position(
                    account_id=account.id,
                    symbol=pos_data.get("symbol", ""),
                    asset_type=pos_data.get("asset_type", ""),
                    underlying_symbol=pos_data.get("underlying_symbol"),
                    option_type=pos_data.get("option_type"),
                    strike_price=pos_data.get("strike_price"),
                    long_quantity=pos_data.get("long_quantity", 0.0),
                    short_quantity=pos_data.get("short_quantity", 0.0),
                    market_value=pos_data.get("market_value", 0.0),
                    average_price=pos_data.get("average_price", 0.0),
                    current_day_profit_loss=pos_data.get("day_change", 0.0),
                    data_source="schwab_import",
                    status="Open",
                    is_active=True,
                    last_updated=datetime.utcnow()
                )
                
                positions_to_add.append(position)
            
            # Bulk insert all positions for this account (MUCH faster)
            print(f"💾 Bulk inserting {len(positions_to_add)} positions...")
            db.add_all(positions_to_add)
            total_positions += len(positions_to_add)
            
            print(f"✅ Account {account.account_number} completed: {len(positions_to_add)} positions")
        
        # Final commit
        print("💾 Committing all changes...")
        db.commit()
        
        result = {
            "message": "Fast import completed successfully!",
            "accounts_imported": len(accounts_data),
            "positions_imported": total_positions,
            "import_timestamp": datetime.utcnow().isoformat()
        }
        
        print(f"🎉 IMPORT COMPLETE: {len(accounts_data)} accounts, {total_positions} positions")
        return result
        
    except Exception as e:
        print(f"❌ Import failed: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/positions")
async def get_all_positions(db: Session = Depends(get_db)):
    """Get all positions from unified table"""
    try:
        positions = db.query(Position).all()
        
        result = []
        for pos in positions:
            result.append({
                "id": pos.id,
                "symbol": pos.symbol,
                "asset_type": pos.asset_type,
                "long_quantity": pos.long_quantity,
                "short_quantity": pos.short_quantity,
                "market_value": pos.market_value,
                "average_price": pos.average_price,
                "data_source": pos.data_source,
                "status": pos.status
            })
        
        return {
            "total_positions": len(result),
            "positions": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts")
async def get_all_accounts(db: Session = Depends(get_db)):
    """Get all accounts from unified table"""
    try:
        accounts = db.query(Account).all()
        
        result = []
        for acc in accounts:
            # Count positions for this account
            position_count = db.query(Position).filter_by(account_id=acc.id).count()
            
            result.append({
                "id": acc.id,
                "account_number": acc.account_number,
                "account_type": acc.account_type,
                "brokerage": acc.brokerage,
                "total_value": acc.total_value,
                "cash_balance": acc.cash_balance,
                "position_count": position_count,
                "last_synced": acc.last_synced.isoformat() if acc.last_synced else None
            })
        
        return {
            "total_accounts": len(result),
            "accounts": result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
