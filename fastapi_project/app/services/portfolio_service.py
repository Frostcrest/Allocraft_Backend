"""
PortfolioService: Business logic for portfolio import/export and unified account/position management.
Extracted from routers/portfolio.py for maintainability and testability.
"""
from sqlalchemy.orm import Session
from datetime import datetime, UTC
from app.models_unified import Account, Position
from app.models import SchwabAccount, SchwabPosition
from app.utils.option_parser import parse_option_symbol
import logging

logger = logging.getLogger(__name__)

class PortfolioService:

    @staticmethod
    def sync_from_schwab_tables(db, deactivate_missing=True):
        from app.models_unified import Account, Position
        from app.models import SchwabAccount, SchwabPosition
        import logging
        logger = logging.getLogger(__name__)
        try:
            # Example: Copy Schwab accounts/positions into unified tables
            schwab_accounts = db.query(SchwabAccount).all()
            schwab_positions = db.query(SchwabPosition).all()
            logger.info(f"Syncing {len(schwab_accounts)} Schwab accounts and {len(schwab_positions)} positions to unified tables")
            # Remove or deactivate existing unified data
            if deactivate_missing:
                db.query(Account).update({Account.is_active: False})
                db.query(Position).update({Position.is_active: False})
            else:
                db.query(Account).delete()
                db.query(Position).delete()
            db.commit()
            # Copy Schwab accounts
            for schwab_acc in schwab_accounts:
                new_acc = Account(
                    account_number=schwab_acc.account_number,
                    account_type=schwab_acc.account_type,
                    brokerage="schwab",
                    hash_value=schwab_acc.hash_value,
                    is_day_trader=schwab_acc.is_day_trader,
                    cash_balance=schwab_acc.cash_balance,
                    buying_power=schwab_acc.buying_power,
                    total_value=schwab_acc.total_value,
                    day_trading_buying_power=schwab_acc.day_trading_buying_power,
                    last_synced=schwab_acc.last_synced,
                    is_active=True
                )
                db.add(new_acc)
                db.flush()
                # Copy positions for this account
                for schwab_pos in db.query(SchwabPosition).filter(SchwabPosition.account_id == schwab_acc.id):
                    new_pos = Position(
                        account_id=new_acc.id,
                        symbol=schwab_pos.symbol,
                        asset_type=schwab_pos.asset_type,
                        underlying_symbol=getattr(schwab_pos, "underlying_symbol", None),
                        option_type=getattr(schwab_pos, "option_type", None),
                        strike_price=getattr(schwab_pos, "strike_price", None),
                        expiration_date=getattr(schwab_pos, "expiration_date", None),
                        long_quantity=getattr(schwab_pos, "long_quantity", 0.0),
                        short_quantity=getattr(schwab_pos, "short_quantity", 0.0),
                        market_value=getattr(schwab_pos, "market_value", 0.0),
                        data_source="schwab_sync",
                        is_active=True
                    )
                    db.add(new_pos)
            db.commit()
            logger.info("Schwab sync to unified tables complete.")
            return {
                "message": "Schwab sync complete",
                "accounts": len(schwab_accounts),
                "positions": len(schwab_positions),
                "accounts_processed": len(schwab_accounts),
                "positions_created": len(schwab_positions)
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Error during Schwab bridge sync: {e}")
            raise

    @staticmethod
    def export_positions(db):
        from datetime import datetime, UTC
        from app.models_unified import Account, Position
        import logging
        logger = logging.getLogger(__name__)
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
                            "quantity": pos.long_quantity - pos.short_quantity,
                            "long_quantity": pos.long_quantity,
                            "short_quantity": pos.short_quantity,
                            "market_value": pos.market_value,
                            "average_price": pos.average_price,
                            "average_long_price": getattr(pos, "average_long_price", None),
                            "average_short_price": getattr(pos, "average_short_price", None),
                            "day_change": getattr(pos, "current_day_profit_loss", None),
                            "day_change_percent": getattr(pos, "current_day_profit_loss_percentage", None),
                            "asset_type": pos.asset_type,
                            "instrument_cusip": getattr(pos, "instrument_cusip", None),
                            "last_updated": pos.last_updated.isoformat() if pos.last_updated else None,
                            "is_active": pos.is_active,
                            "underlying_symbol": pos.underlying_symbol,
                            "option_type": pos.option_type,
                            "strike_price": pos.strike_price,
                            "expiration_date": pos.expiration_date.isoformat() if pos.expiration_date else None,
                            "settled_long_quantity": getattr(pos, "settled_long_quantity", None),
                            "settled_short_quantity": getattr(pos, "settled_short_quantity", None),
                            "long_open_profit_loss": getattr(pos, "long_open_profit_loss", None),
                            "short_open_profit_loss": getattr(pos, "short_open_profit_loss", None),
                            "data_source": pos.data_source,
                            "raw_data": getattr(pos, "raw_data", None)
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
            raise
    @staticmethod
    def list_accounts(db):
        return db.query(Account).filter(Account.is_active == True).all()

    @staticmethod
    def get_positions(db, account_id=None, asset_type=None):
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
        return {
            "total_positions": len(position_data),
            "positions": position_data
        }

    @staticmethod
    def import_positions(import_data: dict, db: Session):
        if "accounts" not in import_data or "export_info" not in import_data:
            raise ValueError("Invalid import data format")
        logger.info(f"Import contains {len(import_data['accounts'])} accounts")
        db.query(Position).delete()
        db.query(Account).delete()
        db.commit()
        imported_accounts = 0
        imported_positions = 0
        for account_data in import_data["accounts"]:
            logger.info(f"Importing account: {account_data['account_number']}")
            new_account = Account(
                account_number=account_data["account_number"],
                account_type=account_data.get("account_type", "UNKNOWN"),
                brokerage="schwab",
                hash_value=account_data.get("hash_value"),
                is_day_trader=account_data.get("is_day_trader", False),
                cash_balance=account_data.get("cash_balance", 0.0),
                buying_power=account_data.get("buying_power", 0.0),
                total_value=account_data.get("total_value", 0.0),
                day_trading_buying_power=account_data.get("day_trading_buying_power", 0.0),
                last_synced=datetime.now(UTC),
                is_active=True
            )
            db.add(new_account)
            db.flush()
            imported_accounts += 1
            position_count = len(account_data.get("positions", []))
            logger.info(f"Importing {position_count} positions for account {account_data['account_number']}")
            for position_data in account_data.get("positions", []):
                underlying_symbol = position_data.get("underlying_symbol")
                if not underlying_symbol and position_data.get("asset_type") == "OPTION":
                    symbol = position_data["symbol"]
                    underlying_symbol = symbol.split()[0] if " " in symbol else symbol
                elif not underlying_symbol:
                    underlying_symbol = position_data["symbol"]
                option_type = position_data.get("option_type")
                strike_price = position_data.get("strike_price")
                expiration_date_str = position_data.get("expiration_date")
                if position_data.get("asset_type") == "OPTION":
                    if not option_type or not strike_price or not expiration_date_str:
                        parsed_option = parse_option_symbol(position_data["symbol"])
                        if parsed_option:
                            option_type = option_type or parsed_option.get("option_type")
                            strike_price = strike_price or parsed_option.get("strike_price")
                            if not expiration_date_str and parsed_option.get("expiry_date"):
                                expiration_date_str = parsed_option.get("expiry_date")
                            logger.info(f"Parsed option symbol {position_data['symbol']}: type={option_type}, strike=${strike_price}, exp={expiration_date_str}")
                new_position = Position(
                    account_id=new_account.id,
                    symbol=position_data["symbol"],
                    asset_type=position_data.get("asset_type", "STOCK"),
                    underlying_symbol=underlying_symbol,
                    option_type=option_type,
                    strike_price=strike_price,
                    expiration_date=expiration_date_str,
                    long_quantity=position_data.get("long_quantity", 0.0),
                    short_quantity=position_data.get("short_quantity", 0.0),
                    market_value=position_data.get("market_value", 0.0),
                    data_source="schwab_import"
                )
                db.add(new_position)
                imported_positions += 1
        db.commit()
        logger.info(f"Imported {imported_accounts} accounts and {imported_positions} positions.")
        return {"accounts": imported_accounts, "positions": imported_positions}
