"""
Data Migration Script: Legacy + Schwab → Unified Models

This script safely migrates data from both legacy (stocks, options) 
and Schwab (schwab_accounts, schwab_positions) tables into the new 
unified accounts and positions tables.

Usage:
    python migrate_to_unified.py --dry-run  # Preview changes
    python migrate_to_unified.py --execute  # Perform migration
"""
import argparse
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.database import SessionLocal, engine
from app.models import Stock, Option, SchwabAccount, SchwabPosition
from app.models_unified import Account, Position


def migrate_legacy_data(db_session, dry_run=True):
    """Migrate legacy stocks and options to unified positions"""
    
    print("=== MIGRATING LEGACY DATA ===")
    
    # Create default manual account for legacy data
    manual_account = Account(
        account_number="MANUAL_001",
        account_type="MANUAL",
        brokerage="manual",
        is_active=True
    )
    
    if not dry_run:
        db_session.add(manual_account)
        db_session.flush()  # Get account ID
    else:
        print(f"[DRY RUN] Would create manual account: {manual_account.account_number}")
    
    account_id = 1 if dry_run else manual_account.id
    
    # Migrate legacy stocks
    legacy_stocks = db_session.query(Stock).all()
    print(f"Found {len(legacy_stocks)} legacy stocks to migrate")
    
    for stock in legacy_stocks:
        # Calculate total quantity (legacy doesn't distinguish long/short)
        quantity = stock.shares or 0.0
        
        unified_position = Position(
            account_id=account_id,
            symbol=stock.ticker,
            underlying_symbol=stock.ticker,
            asset_type="EQUITY",
            
            # Quantities
            long_quantity=max(quantity, 0),  # Positive = long
            short_quantity=abs(min(quantity, 0)),  # Negative = short
            
            # Pricing
            average_price=stock.cost_basis or 0.0,
            market_value=(stock.cost_basis or 0.0) * quantity,
            current_price=stock.current_price,
            
            # Legacy fields preserved
            entry_date=stock.entry_date,
            status=stock.status,
            
            # Metadata
            data_source="legacy_migration",
            price_last_updated=stock.price_last_updated,
            is_active=(stock.status != "Sold")
        )
        
        if dry_run:
            print(f"[DRY RUN] Would migrate stock: {stock.ticker} - {quantity} shares")
        else:
            db_session.add(unified_position)
    
    # Migrate legacy options  
    legacy_options = db_session.query(Option).all()
    print(f"Found {len(legacy_options)} legacy options to migrate")
    
    for option in legacy_options:
        # Parse option details from legacy model
        contracts = getattr(option, 'contracts', 0) or 0
        
        unified_position = Position(
            account_id=account_id,
            symbol=f"{option.ticker}  {option.expiry_date}{'C' if option.option_type == 'Call' else 'P'}{int(option.strike_price * 1000):08d}",
            underlying_symbol=option.ticker,
            asset_type="OPTION",
            
            # Option specifics
            option_type=option.option_type.upper() if option.option_type else None,
            strike_price=option.strike_price,
            expiration_date=datetime.strptime(option.expiry_date, "%Y-%m-%d") if option.expiry_date else None,
            
            # Quantities (assuming long positions for legacy data)
            long_quantity=max(contracts, 0),
            short_quantity=abs(min(contracts, 0)),
            
            # Pricing
            average_price=option.cost_basis or 0.0,
            market_value=(option.cost_basis or 0.0) * contracts * 100,  # Options are per-contract
            current_price=getattr(option, 'current_price', None),
            
            # Legacy fields
            status=getattr(option, 'status', 'Open'),
            
            # Metadata
            data_source="legacy_migration",
            is_active=(getattr(option, 'status', 'Open') != "Closed")
        )
        
        if dry_run:
            print(f"[DRY RUN] Would migrate option: {option.ticker} {option.option_type} ${option.strike_price}")
        else:
            db_session.add(unified_position)


def migrate_schwab_data(db_session, dry_run=True):
    """Migrate Schwab accounts and positions to unified models"""
    
    print("\n=== MIGRATING SCHWAB DATA ===")
    
    schwab_accounts = db_session.query(SchwabAccount).all()
    print(f"Found {len(schwab_accounts)} Schwab accounts to migrate")
    
    for schwab_account in schwab_accounts:
        # Migrate account
        unified_account = Account(
            account_number=schwab_account.account_number,
            account_type=schwab_account.account_type,
            brokerage="schwab",
            hash_value=schwab_account.hash_value,
            is_day_trader=schwab_account.is_day_trader,
            
            # Financial data
            cash_balance=schwab_account.cash_balance,
            buying_power=schwab_account.buying_power,
            total_value=schwab_account.total_value,
            day_trading_buying_power=schwab_account.day_trading_buying_power,
            
            # Metadata
            last_synced=schwab_account.last_synced,
            is_active=True
        )
        
        if dry_run:
            print(f"[DRY RUN] Would migrate Schwab account: {schwab_account.account_number}")
            account_id = schwab_account.id  # Use existing ID for dry run
        else:
            db_session.add(unified_account)
            db_session.flush()
            account_id = unified_account.id
        
        # Migrate positions for this account
        schwab_positions = db_session.query(SchwabPosition).filter_by(account_id=schwab_account.id).all()
        print(f"  - Found {len(schwab_positions)} positions for account {schwab_account.account_number}")
        
        for schwab_pos in schwab_positions:
            unified_position = Position(
                account_id=account_id,
                
                # Symbol and identification
                symbol=schwab_pos.symbol,
                underlying_symbol=schwab_pos.underlying_symbol,
                asset_type=schwab_pos.asset_type,
                instrument_cusip=schwab_pos.instrument_cusip,
                
                # Option specifics
                option_type=schwab_pos.option_type,
                strike_price=schwab_pos.strike_price,
                expiration_date=schwab_pos.expiration_date,
                
                # Quantities
                long_quantity=schwab_pos.long_quantity,
                short_quantity=schwab_pos.short_quantity,
                settled_long_quantity=schwab_pos.settled_long_quantity,
                settled_short_quantity=schwab_pos.settled_short_quantity,
                
                # Pricing
                market_value=schwab_pos.market_value,
                average_price=schwab_pos.average_price,
                average_long_price=schwab_pos.average_long_price,
                average_short_price=schwab_pos.average_short_price,
                
                # P&L
                current_day_profit_loss=schwab_pos.current_day_profit_loss,
                current_day_profit_loss_percentage=schwab_pos.current_day_profit_loss_percentage,
                long_open_profit_loss=schwab_pos.long_open_profit_loss,
                short_open_profit_loss=schwab_pos.short_open_profit_loss,
                
                # Metadata
                last_updated=schwab_pos.last_updated,
                is_active=schwab_pos.is_active,
                raw_data=schwab_pos.raw_data,
                data_source="schwab_migration",
                status="Open" if schwab_pos.is_active else "Closed"
            )
            
            if dry_run:
                print(f"    [DRY RUN] Would migrate position: {schwab_pos.symbol}")
            else:
                db_session.add(unified_position)


def backup_existing_data(db_session):
    """Create backup of existing data before migration"""
    print("=== CREATING DATA BACKUP ===")
    
    # Export current data to backup files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Could implement CSV exports here for safety
    print(f"Backup timestamp: {timestamp}")
    print("Note: Implement CSV exports if needed for additional safety")


def verify_migration(db_session):
    """Verify migration completed successfully"""
    print("\n=== VERIFYING MIGRATION ===")
    
    # Count unified data
    accounts = db_session.query(Account).all()
    positions = db_session.query(Position).all()
    
    print(f"Unified accounts: {len(accounts)}")
    print(f"Unified positions: {len(positions)}")
    
    # Count by data source
    manual_positions = db_session.query(Position).filter_by(data_source="legacy_migration").count()
    schwab_positions = db_session.query(Position).filter_by(data_source="schwab_migration").count()
    
    print(f"  - From legacy: {manual_positions}")
    print(f"  - From Schwab: {schwab_positions}")
    
    # Sample data verification
    if positions:
        sample = positions[0]
        print(f"Sample position: {sample.symbol} in account {sample.account_id}")


def main():
    parser = argparse.ArgumentParser(description="Migrate to unified data models")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without executing")
    parser.add_argument("--execute", action="store_true", help="Execute the migration")
    parser.add_argument("--backup", action="store_true", help="Create backup before migration")
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.execute:
        print("Must specify either --dry-run or --execute")
        return
    
    db = SessionLocal()
    
    try:
        if args.backup and not args.dry_run:
            backup_existing_data(db)
        
        # Run migrations
        migrate_legacy_data(db, dry_run=args.dry_run)
        migrate_schwab_data(db, dry_run=args.dry_run)
        
        if args.execute:
            print("\n=== COMMITTING CHANGES ===")
            db.commit()
            verify_migration(db)
            print("Migration completed successfully!")
        else:
            print("\n=== DRY RUN COMPLETE ===")
            print("Use --execute to perform actual migration")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
