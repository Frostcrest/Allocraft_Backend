from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, UTC
import json
import logging
from ..models import SchwabAccount, SchwabPosition, PositionSnapshot
# from ..core.schwab_client import SchwabClient  # TODO: Implement when core module is created

logger = logging.getLogger(__name__)

class SchwabSyncService:
    def __init__(self, db: Session, schwab_client=None):  # Made schwab_client optional
        self.db = db
        self.schwab_client = schwab_client
    
    async def sync_all_accounts(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Sync all accounts and their positions"""
        try:
            logger.info("Starting full account synchronization")
            
            # Get account summaries from Schwab
            account_summaries = await self.schwab_client.get_account_summaries()
            results = {
                "accounts_synced": 0,
                "positions_updated": 0,
                "positions_added": 0,
                "positions_removed": 0,
                "errors": []
            }
            
            for account_summary in account_summaries:
                account_result = await self.sync_account(
                    account_summary["accountNumber"], 
                    account_summary["hashValue"],
                    force_refresh
                )
                
                # Aggregate results
                results["accounts_synced"] += 1
                results["positions_updated"] += account_result["positions_updated"]
                results["positions_added"] += account_result["positions_added"] 
                results["positions_removed"] += account_result["positions_removed"]
                results["errors"].extend(account_result["errors"])
            
            logger.info(f"Sync completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error during account sync: {str(e)}")
            raise
    
    async def sync_account(self, account_number: str, hash_value: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Sync a specific account and its positions"""
        try:
            # Check if we need to refresh
            account = self.get_or_create_account(account_number, hash_value)
            
            if not force_refresh and self.is_recently_synced(account):
                logger.info(f"Account {account_number} recently synced, skipping")
                return {"positions_updated": 0, "positions_added": 0, "positions_removed": 0, "errors": []}
            
            # Get fresh position data from Schwab
            logger.info(f"Fetching positions for account {account_number}")
            account_details = await self.schwab_client.get_account_details(hash_value, fields="positions")
            
            # Update account information
            self.update_account_info(account, account_details)
            
            # Sync positions
            positions_result = await self.sync_positions(account, account_details.get("securitiesAccount", {}).get("positions", []))
            
            # Create snapshot
            self.create_position_snapshot(account)
            
            # Update last sync time
            account.last_synced = datetime.now(UTC)
            self.db.commit()
            
            logger.info(f"Account {account_number} sync completed: {positions_result}")
            return positions_result
            
        except Exception as e:
            logger.error(f"Error syncing account {account_number}: {str(e)}")
            self.db.rollback()
            return {"positions_updated": 0, "positions_added": 0, "positions_removed": 0, "errors": [str(e)]}
    
    def get_or_create_account(self, account_number: str, hash_value: str) -> SchwabAccount:
        """Get existing account or create new one"""
        account = self.db.query(SchwabAccount).filter(
            SchwabAccount.account_number == account_number
        ).first()
        
        if not account:
            logger.info(f"Creating new account record for {account_number}")
            account = SchwabAccount(
                account_number=account_number,
                hash_value=hash_value
            )
            self.db.add(account)
            self.db.commit()
            self.db.refresh(account)
        else:
            # Update hash value if changed
            if account.hash_value != hash_value:
                account.hash_value = hash_value
                self.db.commit()
        
        return account
    
    def is_recently_synced(self, account: SchwabAccount, minutes: int = 5) -> bool:
        """Check if account was synced recently"""
        if not account.last_synced:
            return False
        threshold = datetime.now(UTC) - timedelta(minutes=minutes)
        return account.last_synced > threshold
    
    def update_account_info(self, account: SchwabAccount, account_details: Dict[str, Any]):
        """Update account-level information"""
        securities_account = account_details.get("securitiesAccount", {})
        current_balances = securities_account.get("currentBalances", {})
        
        account.account_type = securities_account.get("type")
        account.is_day_trader = securities_account.get("isDayTrader", False)
        account.cash_balance = current_balances.get("cashBalance", 0.0)
        account.buying_power = current_balances.get("buyingPower", 0.0)
        account.total_value = current_balances.get("liquidationValue", 0.0)
        account.day_trading_buying_power = current_balances.get("dayTradingBuyingPower", 0.0)
    
    async def sync_positions(self, account: SchwabAccount, positions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Sync positions for an account"""
        current_symbols = set()
        results = {"positions_updated": 0, "positions_added": 0, "positions_removed": 0, "errors": []}
        
        for position_data in positions_data:
            try:
                instrument = position_data.get("instrument", {})
                symbol = instrument.get("symbol")
                
                if not symbol:
                    continue
                
                current_symbols.add(symbol)
                
                # Get or create position
                position = self.db.query(SchwabPosition).filter(
                    and_(
                        SchwabPosition.account_id == account.id,
                        SchwabPosition.symbol == symbol,
                        SchwabPosition.is_active == True
                    )
                ).first()
                
                if position:
                    # Update existing position
                    self.update_position(position, position_data)
                    results["positions_updated"] += 1
                    logger.debug(f"Updated position {symbol}")
                else:
                    # Create new position
                    position = self.create_position(account.id, position_data)
                    results["positions_added"] += 1
                    logger.debug(f"Added new position {symbol}")
                
            except Exception as e:
                logger.error(f"Error processing position {position_data}: {str(e)}")
                results["errors"].append(f"Position {symbol}: {str(e)}")
        
        # Mark positions not in current data as inactive
        inactive_count = self.mark_inactive_positions(account.id, current_symbols)
        results["positions_removed"] = inactive_count
        
        self.db.commit()
        return results
    
    def create_position(self, account_id: int, position_data: Dict[str, Any]) -> SchwabPosition:
        """Create a new position record"""
        instrument = position_data.get("instrument", {})
        
        # Parse option details if applicable
        option_details = self.parse_option_details(instrument)
        
        position = SchwabPosition(
            account_id=account_id,
            symbol=instrument.get("symbol"),
            instrument_cusip=instrument.get("cusip"),
            asset_type=instrument.get("assetType"),
            underlying_symbol=option_details.get("underlying_symbol"),
            option_type=option_details.get("option_type"),
            strike_price=option_details.get("strike_price"),
            expiration_date=option_details.get("expiration_date"),
            raw_data=json.dumps(position_data)
        )
        
        self.update_position_values(position, position_data)
        
        self.db.add(position)
        return position
    
    def update_position(self, position: SchwabPosition, position_data: Dict[str, Any]):
        """Update existing position with new data"""
        self.update_position_values(position, position_data)
        position.last_updated = datetime.now(UTC)
        position.raw_data = json.dumps(position_data)
    
    def update_position_values(self, position: SchwabPosition, position_data: Dict[str, Any]):
        """Update position values from Schwab data"""
        position.long_quantity = position_data.get("longQuantity", 0.0)
        position.short_quantity = position_data.get("shortQuantity", 0.0)
        position.settled_long_quantity = position_data.get("settledLongQuantity", 0.0)
        position.settled_short_quantity = position_data.get("settledShortQuantity", 0.0)
        
        position.market_value = position_data.get("marketValue", 0.0)
        position.average_price = position_data.get("averagePrice", 0.0)
        position.average_long_price = position_data.get("averageLongPrice", 0.0)
        position.average_short_price = position_data.get("averageShortPrice", 0.0)
        
        position.current_day_profit_loss = position_data.get("currentDayProfitLoss", 0.0)
        position.current_day_profit_loss_percentage = position_data.get("currentDayProfitLossPercentage", 0.0)
        position.long_open_profit_loss = position_data.get("longOpenProfitLoss", 0.0)
        position.short_open_profit_loss = position_data.get("shortOpenProfitLoss", 0.0)
    
    def parse_option_details(self, instrument: Dict[str, Any]) -> Dict[str, Any]:
        """Parse option-specific details from instrument data"""
        if instrument.get("assetType") != "OPTION":
            return {}
        
        details = {
            "underlying_symbol": instrument.get("underlyingSymbol"),
            "option_type": instrument.get("putCall")
        }
        
        # Parse expiration and strike from symbol if available
        symbol = instrument.get("symbol", "")
        description = instrument.get("description", "")
        
        # Extract strike price from description
        # Example: "NVIDIA CORP 09/19/2025 $230 Call"
        if "$" in description:
            try:
                strike_text = description.split("$")[1].split()[0]
                details["strike_price"] = float(strike_text)
            except (IndexError, ValueError):
                pass
        
        # Extract expiration date from description
        # Example: "NVIDIA CORP 09/19/2025 $230 Call"
        try:
            date_parts = description.split()
            for part in date_parts:
                if "/" in part and len(part) >= 8:  # MM/DD/YYYY format
                    expiration_date = datetime.strptime(part, "%m/%d/%Y")
                    details["expiration_date"] = expiration_date
                    break
        except (ValueError, IndexError):
            pass
        
        return details
    
    def mark_inactive_positions(self, account_id: int, current_symbols: set) -> int:
        """Mark positions not in current data as inactive"""
        inactive_positions = self.db.query(SchwabPosition).filter(
            and_(
                SchwabPosition.account_id == account_id,
                SchwabPosition.is_active == True,
                ~SchwabPosition.symbol.in_(current_symbols)
            )
        )
        count = inactive_positions.count()
        inactive_positions.update({"is_active": False, "last_updated": datetime.now(UTC)})
        if count > 0:
            logger.info(f"Marked {count} positions as inactive")
        return count
    
    def create_position_snapshot(self, account: SchwabAccount):
        """Create a snapshot of current position state"""
        active_positions = self.db.query(SchwabPosition).filter(
            and_(
                SchwabPosition.account_id == account.id,
                SchwabPosition.is_active == True
            )
        ).all()
        
        # Calculate summary statistics
        total_value = sum(pos.market_value or 0.0 for pos in active_positions)
        total_profit_loss = sum((pos.long_open_profit_loss or 0.0) + (pos.short_open_profit_loss or 0.0) for pos in active_positions)
        
        stock_positions = [pos for pos in active_positions if pos.asset_type == "EQUITY"]
        option_positions = [pos for pos in active_positions if pos.asset_type == "OPTION"]
        
        stock_value = sum(pos.market_value or 0.0 for pos in stock_positions)
        option_value = sum(pos.market_value or 0.0 for pos in option_positions)
        
        snapshot = PositionSnapshot(
            account_id=account.id,
            total_positions=len(active_positions),
            total_value=total_value,
            total_profit_loss=total_profit_loss,
            stock_count=len(stock_positions),
            option_count=len(option_positions),
            stock_value=stock_value,
            option_value=option_value
        )
        
        self.db.add(snapshot)
        logger.debug(f"Created position snapshot for account {account.account_number}")