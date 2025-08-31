import sqlite3
import os

# Check if database exists
db_path = "test.db"
if os.path.exists(db_path):
    print(f"Database {db_path} exists")
    
    # Connect and check tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print(f"Existing tables: {[t[0] for t in tables]}")
    
    # Check if Schwab tables exist
    schwab_tables = ['schwab_accounts', 'schwab_positions', 'position_snapshots']
    existing_schwab_tables = [t[0] for t in tables if t[0] in schwab_tables]
    
    if existing_schwab_tables:
        print(f"Schwab tables already exist: {existing_schwab_tables}")
    else:
        print("No Schwab tables found - need to create them")
    
    conn.close()
else:
    print(f"Database {db_path} does not exist - will be created when first used")
