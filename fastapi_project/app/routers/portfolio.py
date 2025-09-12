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

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/import/positions")
async def import_positions(
    import_data: dict,
    db: Session = Depends(get_db)
):
    """
    Import positions from any brokerage export into unified tables.
    
    Supports:
    - Schwab exports (your current JSON format)
    - Future Fidelity/TD Ameritrade exports
    - Manual CSV imports
    
    No authentication required - development data seeding.
    """
    try:
        logger.info("Starting unified position import")
        
        if "accounts" not in import_data or "export_info" not in import_data:
            raise HTTPException(status_code=400, detail="Invalid import data format")
        
        logger.info(f"Import contains {len(import_data['accounts'])} accounts")
        
        # Clear existing data (development mode)
        logger.info("Clearing existing unified data...")
        db.query(Position).delete()
        db.query(Account).delete()
        db.commit()
        
        imported_accounts = 0
        imported_positions = 0
        
        # Import accounts and positions
        for account_data in import_data["accounts"]:
            logger.info(f"Importing account: {account_data['account_number']}")
            
            # Create unified account
            new_account = Account(
                account_number=account_data["account_number"],
                account_type=account_data.get("account_type", "UNKNOWN"),
                brokerage="schwab",  # Could be detected from export format
                hash_value=account_data.get("hash_value"),
                is_day_trader=account_data.get("is_day_trader", False),
                
                # Financial data
                cash_balance=account_data.get("cash_balance", 0.0),
                buying_power=account_data.get("buying_power", 0.0),
                total_value=account_data.get("total_value", 0.0),
                day_trading_buying_power=account_data.get("day_trading_buying_power", 0.0),
                
                # Metadata
                last_synced=datetime.now(UTC),
                is_active=True
            )
            
            db.add(new_account)
            db.flush()  # Get account ID
            imported_accounts += 1
            
            # Import positions for this account
            position_count = len(account_data.get("positions", []))
            logger.info(f"Importing {position_count} positions for account {account_data['account_number']}")
            
            for position_data in account_data.get("positions", []):
                # Determine underlying symbol for options
                underlying_symbol = position_data.get("underlying_symbol")
                if not underlying_symbol and position_data.get("asset_type") == "OPTION":
                    # Extract from option symbol: "HIMS  251017P00037000" → "HIMS"
                    symbol = position_data["symbol"]
                    underlying_symbol = symbol.split()[0] if " " in symbol else symbol
                elif not underlying_symbol:
                    # For stocks/ETFs, underlying = symbol
                    underlying_symbol = position_data["symbol"]
                
                # Parse option details if this is an option and fields are missing
                option_type = position_data.get("option_type")
                strike_price = position_data.get("strike_price")
                expiration_date_str = position_data.get("expiration_date")
                
                if position_data.get("asset_type") == "OPTION":
                    # Try to parse option symbol if any fields are missing
                    if not option_type or not strike_price or not expiration_date_str:
                        parsed_option = parse_option_symbol(position_data["symbol"])
                        if parsed_option:
                            option_type = option_type or parsed_option.get("option_type")
                            strike_price = strike_price or parsed_option.get("strike_price")
                            if not expiration_date_str and parsed_option.get("expiry_date"):
                                expiration_date_str = parsed_option.get("expiry_date")
                            
                            logger.info(f"Parsed option symbol {position_data['symbol']}: "
                                      f"type={option_type}, strike=${strike_price}, exp={expiration_date_str}")
                
                # Create unified position
                new_position = Position(
                    account_id=new_account.id,
                    
                    # Symbol and identification
                    symbol=position_data["symbol"],
                    underlying_symbol=underlying_symbol,
                    asset_type=position_data.get("asset_type", "UNKNOWN"),
                    instrument_cusip=position_data.get("instrument_cusip"),
                    
                    # Option-specific fields
                    option_type=option_type,
                    strike_price=strike_price,
                    
                    # Quantities
                    long_quantity=position_data.get("long_quantity", 0.0),
                    short_quantity=position_data.get("short_quantity", 0.0),
                    settled_long_quantity=position_data.get("settled_long_quantity", 0.0),
                    settled_short_quantity=position_data.get("settled_short_quantity", 0.0),
                    
                    # Pricing and value
                    market_value=position_data.get("market_value", 0.0),
                    average_price=position_data.get("average_price", 0.0),
                    average_long_price=position_data.get("average_long_price", 0.0),
                    average_short_price=position_data.get("average_short_price", 0.0),
                    
                    # P&L tracking
                    current_day_profit_loss=position_data.get("day_change", 0.0),
                    current_day_profit_loss_percentage=position_data.get("day_change_percent", 0.0),
                    long_open_profit_loss=position_data.get("long_open_profit_loss", 0.0),
                    short_open_profit_loss=position_data.get("short_open_profit_loss", 0.0),
                    
                    # Status and metadata
                    status="Open" if position_data.get("is_active", True) else "Closed",
                    is_active=position_data.get("is_active", True),
                    raw_data=json.dumps(position_data) if position_data.get("raw_data") else None,
                    last_updated=datetime.now(UTC),
                    data_source="schwab_import"  # Track import source
                )
                
                # Handle expiration date
                if expiration_date_str:
                    try:
                        # Handle different date formats
                        if "T" in expiration_date_str or "Z" in expiration_date_str:
                            # ISO format with time
                            new_position.expiration_date = datetime.fromisoformat(
                                expiration_date_str.replace("Z", "+00:00")
                            )
                        else:
                            # Simple date format (YYYY-MM-DD)
                            new_position.expiration_date = datetime.fromisoformat(expiration_date_str)
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Invalid expiration date: {expiration_date_str}, error: {e}")
                
                db.add(new_position)
                imported_positions += 1
        
        db.commit()
        
        result = {
            "message": "Positions imported successfully to unified tables",
            "accounts_created": imported_accounts,
            "positions_created": imported_positions,
            "import_timestamp": datetime.now(UTC).isoformat(),
            "source_export": import_data["export_info"],
            "data_source": "schwab_import"
        }
        
        logger.info(f"Successfully imported {imported_accounts} accounts with {imported_positions} positions")
        
        return result
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error importing positions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import positions: {str(e)}")


@router.get("/accounts")
async def get_accounts(db: Session = Depends(get_db)):
    """Get all accounts from unified tables"""
    try:
        accounts = db.query(Account).all()
        return [
            {
                "id": acc.id,
                "account_number": acc.account_number,
                "account_type": acc.account_type,
                "brokerage": acc.brokerage,
                "total_value": acc.total_value,
                "cash_balance": acc.cash_balance,
                "buying_power": acc.buying_power,
                "last_synced": acc.last_synced.isoformat() if acc.last_synced else None,
                "is_active": acc.is_active
            }
            for acc in accounts
        ]
    except Exception as e:
        logger.error(f"Error getting accounts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_positions(
    account_id: int = None,
    asset_type: str = None,
    db: Session = Depends(get_db)
):
    """Get positions from unified tables with optional filtering"""
    try:
        query = db.query(Position).filter(Position.is_active == True)
        
        if account_id:
            query = query.filter(Position.account_id == account_id)
        
        if asset_type:
            query = query.filter(Position.asset_type == asset_type)
        
        positions = query.all()
        
        position_data = [
            {
                "id": pos.id,
                "account_id": pos.account_id,
                "symbol": pos.symbol,
                "underlying_symbol": pos.underlying_symbol,
                "asset_type": pos.asset_type,
                "option_type": pos.option_type,
                "strike_price": pos.strike_price,
                "expiration_date": pos.expiration_date.isoformat() if pos.expiration_date else None,
                "long_quantity": pos.long_quantity,
                "short_quantity": pos.short_quantity,
                "market_value": pos.market_value,
                "average_price": pos.average_price,
                "current_day_profit_loss": pos.current_day_profit_loss,
                "status": pos.status,
                "data_source": pos.data_source,
                "last_updated": pos.last_updated.isoformat() if pos.last_updated else None
            }
            for pos in positions
        ]
        
        # Return in the format expected by frontend
        return {
            "total_positions": len(position_data),
            "positions": position_data
        }
        
    except Exception as e:
        logger.error(f"Error getting positions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/from-schwab-tables")
def sync_from_schwab_tables(
    deactivate_missing: bool = True,
    db: Session = Depends(get_db),
    _: dict = Depends(require_role("admin"))
):
    """Bridge existing Schwab tables into unified Account/Position.

    This copies rows from schwab_accounts and schwab_positions into unified
    accounts/positions with upsert-like behavior and data_source="schwab_bridge".

    - Creates or updates unified Account by account_number
    - Upserts Positions by (account_id, symbol) scoped to data_source="schwab_bridge"
    - Optionally deactivates prior unified positions from this bridge that are no longer present
    """
    try:
        accounts = db.query(SchwabAccount).all()
        acc_created = acc_updated = 0
        pos_created = pos_updated = pos_deactivated = 0

        for s_acc in accounts:
            # Upsert unified account
            u_acc = db.query(Account).filter(Account.account_number == s_acc.account_number).first()
            if not u_acc:
                u_acc = Account(account_number=s_acc.account_number)
                db.add(u_acc)
                acc_created += 1
            else:
                acc_updated += 1

            # Always set these fields from Schwab source
            u_acc.account_type = getattr(s_acc, "account_type", None) or u_acc.account_type
            u_acc.brokerage = "schwab"
            u_acc.hash_value = getattr(s_acc, "hash_value", None) or u_acc.hash_value
            u_acc.is_day_trader = bool(getattr(s_acc, "is_day_trader", False))
            u_acc.cash_balance = float(getattr(s_acc, "cash_balance", 0.0) or 0.0)
            u_acc.buying_power = float(getattr(s_acc, "buying_power", 0.0) or 0.0)
            u_acc.total_value = float(getattr(s_acc, "total_value", 0.0) or 0.0)
            u_acc.day_trading_buying_power = float(getattr(s_acc, "day_trading_buying_power", 0.0) or 0.0)
            u_acc.last_synced = datetime.now(UTC)
            u_acc.is_active = True
            db.flush()

            # Collect current symbols for deactivation logic
            current_symbols = set()

            s_positions = db.query(SchwabPosition).filter(
                SchwabPosition.account_id == s_acc.id,
                SchwabPosition.is_active == True,
            ).all()

            for s_pos in s_positions:
                symbol = s_pos.symbol
                if not symbol:
                    continue
                current_symbols.add(symbol)

                u_pos = db.query(Position).filter(
                    Position.account_id == u_acc.id,
                    Position.symbol == symbol,
                    Position.data_source == "schwab_bridge",
                ).first()

                creating = False
                if not u_pos:
                    u_pos = Position(account_id=u_acc.id, symbol=symbol)
                    u_pos.data_source = "schwab_bridge"
                    db.add(u_pos)
                    creating = True

                # Map core fields
                u_pos.underlying_symbol = getattr(s_pos, "underlying_symbol", None) or symbol
                u_pos.asset_type = getattr(s_pos, "asset_type", None) or u_pos.asset_type or "UNKNOWN"
                u_pos.instrument_cusip = getattr(s_pos, "instrument_cusip", None)

                # Options
                u_pos.option_type = getattr(s_pos, "option_type", None)
                u_pos.strike_price = getattr(s_pos, "strike_price", None)
                u_pos.expiration_date = getattr(s_pos, "expiration_date", None)

                # Quantities
                u_pos.long_quantity = float(getattr(s_pos, "long_quantity", 0.0) or 0.0)
                u_pos.short_quantity = float(getattr(s_pos, "short_quantity", 0.0) or 0.0)
                u_pos.settled_long_quantity = float(getattr(s_pos, "settled_long_quantity", 0.0) or 0.0)
                u_pos.settled_short_quantity = float(getattr(s_pos, "settled_short_quantity", 0.0) or 0.0)

                # Pricing / P&L
                u_pos.market_value = float(getattr(s_pos, "market_value", 0.0) or 0.0)
                u_pos.average_price = float(getattr(s_pos, "average_price", 0.0) or 0.0)
                u_pos.average_long_price = float(getattr(s_pos, "average_long_price", 0.0) or 0.0)
                u_pos.average_short_price = float(getattr(s_pos, "average_short_price", 0.0) or 0.0)
                u_pos.current_day_profit_loss = float(getattr(s_pos, "current_day_profit_loss", 0.0) or 0.0)
                u_pos.current_day_profit_loss_percentage = float(getattr(s_pos, "current_day_profit_loss_percentage", 0.0) or 0.0)
                u_pos.long_open_profit_loss = float(getattr(s_pos, "long_open_profit_loss", 0.0) or 0.0)
                u_pos.short_open_profit_loss = float(getattr(s_pos, "short_open_profit_loss", 0.0) or 0.0)

                # Metadata
                u_pos.is_active = True
                u_pos.status = "Open"
                u_pos.last_updated = datetime.now(UTC)
                try:
                    u_pos.raw_data = s_pos.raw_data
                except Exception:
                    pass

                if creating:
                    pos_created += 1
                else:
                    pos_updated += 1

            # Deactivate missing positions for this account from this bridge
            if deactivate_missing:
                q_inactive = db.query(Position).filter(
                    Position.account_id == u_acc.id,
                    Position.data_source == "schwab_bridge",
                    Position.is_active == True,
                )
                # Only those not present now
                if current_symbols:
                    q_inactive = q_inactive.filter(~Position.symbol.in_(list(current_symbols)))
                stale_positions = q_inactive.all()
                for p in stale_positions:
                    p.is_active = False
                    p.status = "Closed"
                    p.last_updated = datetime.now(UTC)
                    pos_deactivated += 1

        db.commit()

        return {
            "message": "Schwab tables synced into unified models",
            "accounts_processed": len(accounts),
            "accounts_created": acc_created,
            "accounts_updated": acc_updated,
            "positions_created": pos_created,
            "positions_updated": pos_updated,
            "positions_deactivated": pos_deactivated,
            "timestamp": datetime.now(UTC).isoformat(),
            "data_source": "schwab_bridge",
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error during Schwab bridge sync: {e}")
        raise HTTPException(status_code=500, detail=f"Bridge sync failed: {str(e)}")


@router.get("/positions/stocks")
async def get_stock_positions(db: Session = Depends(get_db)):
    """Get only stock positions (EQUITY) - legacy compatibility"""
    result = await get_positions(asset_type="EQUITY", db=db)
    return result["positions"]  # Return just the array for legacy compatibility


@router.get("/positions/options")
async def get_option_positions(db: Session = Depends(get_db)):
    """Get only option positions - legacy compatibility"""
    result = await get_positions(asset_type="OPTION", db=db)
    return result["positions"]  # Return just the array for legacy compatibility


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
        accounts = db.query(Account).filter(Account.is_active == True).all()
        
        export_data = {
            "export_info": {
                "export_timestamp": datetime.now(UTC).isoformat(),
                "total_accounts": len(accounts),
                "total_positions": 0,
                "source": "unified_tables"
            },
            "accounts": []
        }
        
        for account in accounts:
            positions = db.query(Position).filter(
                Position.account_id == account.id,
                Position.is_active == True
            ).all()
            
            account_data = {
                "account_number": account.account_number,
                "account_type": account.account_type,
                "brokerage": account.brokerage,
                "hash_value": account.hash_value,
                "is_day_trader": account.is_day_trader,
                "buying_power": account.buying_power,
                "cash_balance": account.cash_balance,
                "total_value": account.total_value,
                "day_trading_buying_power": account.day_trading_buying_power,
                "last_synced": account.last_synced.isoformat() if account.last_synced else None,
                "total_positions": len(positions),
                "positions": [
                    {
                        "symbol": pos.symbol,
                        "quantity": pos.long_quantity - pos.short_quantity,  # Net quantity
                        "long_quantity": pos.long_quantity,
                        "short_quantity": pos.short_quantity,
                        "market_value": pos.market_value,
                        "average_price": pos.average_price,
                        "average_long_price": pos.average_long_price,
                        "average_short_price": pos.average_short_price,
                        "day_change": pos.current_day_profit_loss,
                        "day_change_percent": pos.current_day_profit_loss_percentage,
                        "asset_type": pos.asset_type,
                        "instrument_cusip": pos.instrument_cusip,
                        "last_updated": pos.last_updated.isoformat() if pos.last_updated else None,
                        "is_active": pos.is_active,
                        "underlying_symbol": pos.underlying_symbol,
                        "option_type": pos.option_type,
                        "strike_price": pos.strike_price,
                        "expiration_date": pos.expiration_date.isoformat() if pos.expiration_date else None,
                        "settled_long_quantity": pos.settled_long_quantity,
                        "settled_short_quantity": pos.settled_short_quantity,
                        "long_open_profit_loss": pos.long_open_profit_loss,
                        "short_open_profit_loss": pos.short_open_profit_loss,
                        "data_source": pos.data_source,
                        "raw_data": pos.raw_data
                    }
                    for pos in positions
                ]
            }
            
            export_data["accounts"].append(account_data)
            export_data["export_info"]["total_positions"] += len(positions)
        
        logger.info(f"Exported {len(accounts)} accounts with {export_data['export_info']['total_positions']} positions")
        
        return export_data
        
    except Exception as e:
        logger.error(f"Error exporting positions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export positions: {str(e)}")
