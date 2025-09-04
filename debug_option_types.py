import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

# Change to the fastapi_project directory so the database path is correct
os.chdir(os.path.join(os.path.dirname(__file__), 'fastapi_project'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi_project.app.models_unified import Position

def check_option_types():
    """Check what option_type values are in the database"""
    print("=== DATABASE OPTION_TYPE VALUES ===")
    
    DATABASE_URL = "sqlite:///./test.db"
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    try:
        # Get all option positions
        option_positions = db.query(Position).filter(Position.is_option == True).all()
        
        print(f"Found {len(option_positions)} option positions")
        
        option_types = set()
        for pos in option_positions:
            option_types.add(pos.option_type)
            print(f"Symbol: {pos.symbol}, Option Type: '{pos.option_type}', Strike: {pos.strike_price}")
        
        print(f"\nUnique option_type values: {option_types}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_option_types()
