"""
Fast Portfolio Import with Progress Tracking
Optimized for speed and transparency
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.dependencies import require_authenticated_user
from app.models_unified import Account, Position
from datetime import datetime, UTC
import logging

router = APIRouter(
    prefix="/portfolio",
    tags=["portfolio"],
    dependencies=[Depends(require_authenticated_user)],
)
logger = logging.getLogger(__name__)

@router.post("/import-fast")
def import_positions_fast(import_data: dict, db: Session = Depends(get_db)):
    """
    Fast import with progress tracking - optimized for large datasets
    """
    try:
        logger.info("🚀 Starting fast import...")
        
        # Validate input
        if "accounts" not in import_data:
            raise HTTPException(status_code=400, detail="Missing 'accounts' in import data")
        
        accounts_data = import_data["accounts"]
        logger.info(f"📊 Found {len(accounts_data)} accounts to import")
        
        # Clear existing data first (fast operation)
        logger.info("🧹 Clearing existing unified data...")
        db.query(Position).delete()
        db.query(Account).delete()
        db.commit()
        logger.info("✅ Existing data cleared")
        
        total_positions = 0
        
        # Process each account
        for i, account_data in enumerate(accounts_data):
            logger.info(f"📁 Processing account {i+1}/{len(accounts_data)}: {account_data.get('account_number', 'Unknown')}")
            
            # Create account (simple, fast)
            account = Account(
                account_number=account_data["account_number"],
                account_type=account_data.get("account_type", ""),
                brokerage="schwab",
                total_value=account_data.get("total_value", 0.0),
                cash_balance=account_data.get("cash_balance", 0.0),
                buying_power=account_data.get("buying_power", 0.0),
                last_synced=datetime.now(UTC)
            )
            
            db.add(account)
            db.flush()  # Get ID immediately
            logger.debug(f"✅ Account created with ID: {account.id}")
            
            # Prepare positions in batches (much faster)
            positions_data = account_data.get("positions", [])
            logger.info(f"📈 Processing {len(positions_data)} positions...")
            
            positions_to_add = []
            
            for j, pos_data in enumerate(positions_data):
                # Show progress every 5 positions
                if j % 5 == 0:
                    logger.debug(f"  📊 Processing position {j+1}/{len(positions_data)}: {pos_data.get('symbol', 'Unknown')}")
                
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
                    last_updated=datetime.now(UTC)
                )
                
                positions_to_add.append(position)
            
            # Bulk insert all positions for this account (MUCH faster)
            logger.info(f"💾 Bulk inserting {len(positions_to_add)} positions...")
            db.add_all(positions_to_add)
            total_positions += len(positions_to_add)
            
            logger.info(f"✅ Account {account.account_number} completed: {len(positions_to_add)} positions")
        
        # Final commit
        logger.info("💾 Committing all changes...")
        db.commit()
        
        result = {
            "message": "Fast import completed successfully!",
            "accounts_imported": len(accounts_data),
            "positions_imported": total_positions,
            "import_timestamp": datetime.now(UTC).isoformat()
        }
        
        logger.info(f"🎉 IMPORT COMPLETE: {len(accounts_data)} accounts, {total_positions} positions")
        return result
        
    except Exception as e:
        logger.error(f"❌ Import failed: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/positions")
def get_all_positions(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
):
    """Get positions from unified table with pagination"""
    try:
        total = db.query(Position).count()
        positions = db.query(Position).offset(offset).limit(limit).all()
        
        items = []
        for pos in positions:
            items.append({
                "id": pos.id,
                "account_id": pos.account_id,
                "symbol": pos.symbol,
                "underlying_symbol": pos.underlying_symbol,
                "asset_type": pos.asset_type,
                "option_type": pos.option_type,
                "strike_price": pos.strike_price,
                "expiration_date": pos.expiration_date,
                "long_quantity": pos.long_quantity,
                "short_quantity": pos.short_quantity,
                "market_value": pos.market_value,
                "average_price": pos.average_price,
                "current_price": pos.current_price,
                "price_last_updated": pos.price_last_updated,
                "current_day_profit_loss": pos.current_day_profit_loss,
                "status": pos.status,
                "data_source": pos.data_source,
                "last_updated": pos.last_updated
            })
        
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stocks")
def get_stock_positions(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
):
    """Get stock positions from unified table with optional pagination"""
    try:
        from app.utils.option_parser import parse_option_symbol
        
        # Get stock positions (EQUITY and COLLECTIVE_INVESTMENT)
        base_q = db.query(Position).filter(
            Position.asset_type.in_(["EQUITY", "COLLECTIVE_INVESTMENT"])
        )
        total = base_q.count()
        stock_positions = base_q.offset(offset).limit(limit).all()
        
        result = []
        for pos in stock_positions:
            # Calculate profit/loss
            market_value = pos.market_value or 0
            cost_basis = (pos.average_price or 0) * (pos.long_quantity or 0)
            profit_loss = market_value - cost_basis
            profit_loss_percent = ((profit_loss / cost_basis) * 100) if cost_basis > 0 else 0
            
            result.append({
                "id": pos.id,
                "symbol": pos.symbol,
                "asset_type": pos.asset_type,
                "long_quantity": pos.long_quantity or 0,
                "short_quantity": pos.short_quantity or 0,
                "market_value": market_value,
                "average_price": pos.average_price or 0,
                "current_price": pos.current_price or 0,
                "data_source": pos.data_source,
                "status": pos.status,
                "account_id": pos.account_id,
                "profit_loss": profit_loss,
                "profit_loss_percent": profit_loss_percent
            })
        
        return {"items": result, "total": total, "limit": limit, "offset": offset}
        
    except Exception as e:
        logger.error(f"Error fetching stock positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options")
def get_option_positions(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500, description="Max items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
):
    """Get option positions from unified table with enhanced P&L calculations"""
    try:
        from app.utils.option_parser import parse_option_symbol
        from app.services.pnl_service import OptionPnLCalculator
        
        # Get option positions
        base_q = db.query(Position).filter(Position.asset_type == "OPTION")
        total = base_q.count()
        option_positions = base_q.offset(offset).limit(limit).all()
        
        result = []
        for pos in option_positions:
            # Parse option symbol to get additional details
            parsed = parse_option_symbol(pos.symbol)
            
            # Calculate contracts (positive for long, negative for short)
            contracts = (pos.long_quantity or 0) - (pos.short_quantity or 0)
            
            # Prepare position data for enhanced P&L calculation
            position_data = {
                'contracts': contracts,
                'average_price': pos.average_price or 0,
                'current_price': pos.current_price or 0,
                'option_type': parsed.get('option_type', 'CALL') if parsed else 'CALL',
                'strike_price': parsed.get('strike_price', 0) if parsed else 0,
                'symbol': pos.symbol
            }
            
            # Determine strategy type based on position characteristics
            strategy_type = None
            if contracts < 0:  # Short position
                if position_data['option_type'] == 'PUT':
                    strategy_type = 'wheel'  # Cash-secured put
                elif position_data['option_type'] == 'CALL':
                    strategy_type = 'covered_call'  # Assume covered call
            
            # Calculate enhanced P&L using new service
            pnl_data = OptionPnLCalculator.calculate_strategy_pnl(position_data, strategy_type)
            
            option_data = {
                "id": pos.id,
                "symbol": pos.symbol,
                "asset_type": pos.asset_type,
                "long_quantity": pos.long_quantity or 0,
                "short_quantity": pos.short_quantity or 0,
                "market_value": pnl_data['market_value'],
                "average_price": pos.average_price or 0,
                "current_price": pos.current_price or 0,
                "data_source": pos.data_source,
                "status": pos.status,
                "account_id": pos.account_id,
                "contracts": contracts,
                "profit_loss": pnl_data['profit_loss'],
                "profit_loss_percent": pnl_data['profit_loss_percent'],
                "cost_basis": pnl_data['cost_basis'],
                "strategy_type": pnl_data.get('strategy_type'),
                "risk_level": pnl_data.get('risk_level'),
                "breakeven_price": pnl_data.get('breakeven_price'),
                "max_profit": pnl_data.get('max_profit'),
                "calculation_timestamp": pnl_data.get('calculation_timestamp')
            }
            
            # Add parsed option details if parsing was successful
            if parsed:
                option_data.update({
                    "ticker": parsed["ticker"],
                    "option_type": parsed["option_type"],
                    "strike_price": parsed["strike_price"],
                    "expiration_date": parsed["expiry_date"]
                })
            else:
                # Fallback values if parsing failed
                option_data.update({
                    "ticker": pos.symbol.split()[0] if ' ' in pos.symbol else pos.symbol,
                    "option_type": "Unknown",
                    "strike_price": 0,
                    "expiration_date": None
                })
            
            result.append(option_data)
        
        return {"items": result, "total": total, "limit": limit, "offset": offset}
        
    except Exception as e:
        logger.error(f"Error fetching option positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/options/analytics")
def get_option_analytics(db: Session = Depends(get_db)):
    """Get portfolio-level option analytics and P&L summary"""
    try:
        from app.services.pnl_service import OptionPnLCalculator
        from app.utils.option_parser import parse_option_symbol
        
        # Get all option positions
        option_positions = db.query(Position).filter(
            Position.asset_type == "OPTION"
        ).all()
        
        # Prepare position data for portfolio calculation
        positions_data = []
        for pos in option_positions:
            parsed = parse_option_symbol(pos.symbol)
            contracts = (pos.long_quantity or 0) - (pos.short_quantity or 0)
            
            # Determine strategy type
            strategy_type = 'unknown'
            if contracts < 0:  # Short position
                if parsed and parsed.get('option_type') == 'PUT':
                    strategy_type = 'wheel'
                elif parsed and parsed.get('option_type') == 'CALL':
                    strategy_type = 'covered_call'
            elif contracts > 0:  # Long position
                strategy_type = 'long_option'
            
            position_data = {
                'contracts': contracts,
                'average_price': pos.average_price or 0,
                'current_price': pos.current_price or 0,
                'option_type': parsed.get('option_type', 'CALL') if parsed else 'CALL',
                'strike_price': parsed.get('strike_price', 0) if parsed else 0,
                'symbol': pos.symbol,
                'strategy_type': strategy_type
            }
            positions_data.append(position_data)
        
        # Calculate portfolio-level analytics
        portfolio_analytics = OptionPnLCalculator.calculate_portfolio_pnl(positions_data)
        
        return {
            "portfolio_summary": portfolio_analytics,
            "position_count": len(positions_data),
            "last_updated": portfolio_analytics.get('calculation_timestamp')
        }
        
    except Exception as e:
        logger.error(f"Error calculating option analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/accounts")
def get_all_accounts(db: Session = Depends(get_db)):
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


@router.post("/refresh-all-prices")
def refresh_all_portfolio_prices(db: Session = Depends(get_db)):
    """
    Refresh current prices for all active portfolio positions (stocks and options)
    with market value recalculation and detailed progress reporting
    """
    try:
        from app.services.market_value_service import MarketValueUpdateService
        
        # Initialize the market value update service
        update_service = MarketValueUpdateService(db)
        
        # Perform full portfolio price refresh
        result = update_service.refresh_all_portfolio_prices()
        
        if result["success"]:
            return result
        else:
            raise HTTPException(
                status_code=500,
                detail=result["message"]
            )
            
    except Exception as e:
        logger.error(f"Error in refresh_all_portfolio_prices: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh portfolio prices: {str(e)}"
        )


@router.post("/refresh-selected-prices")
def refresh_selected_position_prices(
    position_ids: List[int],
    db: Session = Depends(get_db)
):
    """
    Refresh current prices for selected positions only
    """
    try:
        from app.services.market_value_service import MarketValueUpdateService
        
        if not position_ids:
            raise HTTPException(
                status_code=400,
                detail="No position IDs provided"
            )
        
        # Initialize the market value update service
        update_service = MarketValueUpdateService(db)
        
        # Perform selected positions price refresh
        result = update_service.refresh_selected_positions(position_ids)
        
        if result["success"]:
            return result
        else:
            raise HTTPException(
                status_code=500,
                detail=result["message"]
            )
            
    except Exception as e:
        logger.error(f"Error in refresh_selected_position_prices: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh selected position prices: {str(e)}"
        )
