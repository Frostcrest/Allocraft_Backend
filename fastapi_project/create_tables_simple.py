import sqlite3
import os
from datetime import datetime

def create_schwab_tables():
    print("🔄 Creating Schwab database tables...")
    
    # Connect to the database
    db_path = "test.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create schwab_accounts table
        print("📋 Creating schwab_accounts table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schwab_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_number TEXT UNIQUE NOT NULL,
                hash_value TEXT NOT NULL,
                account_type TEXT,
                is_day_trader BOOLEAN DEFAULT FALSE,
                last_synced DATETIME DEFAULT CURRENT_TIMESTAMP,
                cash_balance REAL DEFAULT 0.0,
                buying_power REAL DEFAULT 0.0,
                total_value REAL DEFAULT 0.0,
                day_trading_buying_power REAL DEFAULT 0.0
            )
        """)
        
        # Create indexes for schwab_accounts
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_schwab_accounts_account_number ON schwab_accounts(account_number)")
        
        # Create schwab_positions table
        print("📋 Creating schwab_positions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schwab_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                instrument_cusip TEXT,
                asset_type TEXT,
                underlying_symbol TEXT,
                option_type TEXT,
                strike_price REAL,
                expiration_date DATETIME,
                long_quantity REAL DEFAULT 0.0,
                short_quantity REAL DEFAULT 0.0,
                settled_long_quantity REAL DEFAULT 0.0,
                settled_short_quantity REAL DEFAULT 0.0,
                market_value REAL DEFAULT 0.0,
                average_price REAL DEFAULT 0.0,
                average_long_price REAL DEFAULT 0.0,
                average_short_price REAL DEFAULT 0.0,
                current_day_profit_loss REAL DEFAULT 0.0,
                current_day_profit_loss_percentage REAL DEFAULT 0.0,
                long_open_profit_loss REAL DEFAULT 0.0,
                short_open_profit_loss REAL DEFAULT 0.0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                raw_data TEXT,
                FOREIGN KEY (account_id) REFERENCES schwab_accounts(id)
            )
        """)
        
        # Create indexes for schwab_positions
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_schwab_positions_symbol ON schwab_positions(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_schwab_positions_underlying_symbol ON schwab_positions(underlying_symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_schwab_positions_account_id ON schwab_positions(account_id)")
        
        # Create position_snapshots table
        print("📋 Creating position_snapshots table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS position_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                snapshot_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_positions INTEGER DEFAULT 0,
                total_value REAL DEFAULT 0.0,
                total_profit_loss REAL DEFAULT 0.0,
                stock_count INTEGER DEFAULT 0,
                option_count INTEGER DEFAULT 0,
                stock_value REAL DEFAULT 0.0,
                option_value REAL DEFAULT 0.0,
                FOREIGN KEY (account_id) REFERENCES schwab_accounts(id)
            )
        """)
        
        # Create index for position_snapshots
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_position_snapshots_account_id ON position_snapshots(account_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_position_snapshots_date ON position_snapshots(snapshot_date)")
        
        # Commit the changes
        conn.commit()
        
        print("✅ Schwab tables created successfully!")
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'schwab_%' OR name LIKE 'position_%'")
        new_tables = cursor.fetchall()
        print(f"📊 Created tables: {[t[0] for t in new_tables]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating tables: {str(e)}")
        conn.rollback()
        return False
        
    finally:
        conn.close()

if __name__ == "__main__":
    success = create_schwab_tables()
    
    if success:
        print("\n🎉 Database migration completed successfully!")
        print("\nNext steps:")
        print("1. Restart your FastAPI server if it's running")
        print("2. Navigate to the Stocks page in the frontend")
        print("3. Click 'Sync Fresh Data' to populate the database")
    else:
        print("\n❌ Database migration failed!")
