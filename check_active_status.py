import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

# Change to the fastapi_project directory so the database path is correct
os.chdir(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

from fastapi_project.app.database import SessionLocal
from fastapi_project.app.models_unified import Position

def check_active_positions():
    """Check is_active field on positions"""
    db = SessionLocal()
    try:
        # Get all positions and check is_active field
        all_positions = db.query(Position).all()
        print(f"Total positions in DB: {len(all_positions)}")
        
        active_positions = db.query(Position).filter(Position.is_active == True).all()
        print(f"Active positions: {len(active_positions)}")
        
        # Check a few specific positions
        print("\nSample positions with is_active status:")
        for pos in all_positions[:5]:
            print(f"  {pos.symbol} ({pos.asset_type}): is_active={pos.is_active}, account_id={pos.account_id}")
        
        # Check if we have any short puts that are active
        short_puts = []
        for pos in all_positions:
            if pos.asset_type == "OPTION" and pos.option_type == "PUT" and pos.short_quantity > 0:
                short_puts.append(pos)
                print(f"Short PUT: {pos.symbol} - is_active={pos.is_active}, account_id={pos.account_id}")
        
        print(f"\nTotal short puts found: {len(short_puts)}")
        active_short_puts = [p for p in short_puts if p.is_active]
        print(f"Active short puts: {len(active_short_puts)}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_active_positions()
