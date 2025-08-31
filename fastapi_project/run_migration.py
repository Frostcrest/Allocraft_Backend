"""
Run this script to create the Schwab tables in your database
Usage: python run_migration.py
"""
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir.absolute()))

try:
    print("🔄 Creating Schwab database tables...")
    
    # Import after adding to path
    from database import Base, engine
    from models.schwab_models import SchwabAccount, SchwabPosition, PositionSnapshot
    
    # Create the tables
    print("📋 Creating tables: schwab_accounts, schwab_positions, position_snapshots")
    
    Base.metadata.create_all(bind=engine, tables=[
        SchwabAccount.__table__,
        SchwabPosition.__table__,
        PositionSnapshot.__table__
    ])
    
    print("✅ Database migration completed successfully!")
    print("\nNext steps:")
    print("1. Restart your FastAPI server if it's running")
    print("2. Navigate to the Stocks page in the frontend")
    print("3. Click 'Sync Fresh Data' to populate the database")
    
except Exception as e:
    print(f"❌ Error during migration: {str(e)}")
    print(f"❌ Error type: {type(e).__name__}")
    
    # More detailed error info for debugging
    import traceback
    print("\nDetailed error traceback:")
    traceback.print_exc()
    
    print("\nTroubleshooting:")
    print("1. Make sure you're in the Allocraft_Backend/fastapi_project directory")
    print("2. Check that your database file is accessible")
    print("3. Ensure all dependencies are installed (pip install -r requirements.txt)")
    
    sys.exit(1)
