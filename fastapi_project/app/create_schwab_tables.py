"""
Script to create Schwab tables
Run this to add the new tables to your database
"""
from sqlalchemy import create_engine
from .database import Base, engine
from .models.schwab_models import SchwabAccount, SchwabPosition, PositionSnapshot

def create_schwab_tables():
    print("Creating Schwab tables...")
    
    # Create the tables using the existing engine
    Base.metadata.create_all(bind=engine, tables=[
        SchwabAccount.__table__,
        SchwabPosition.__table__,
        PositionSnapshot.__table__
    ])
    
    print("✅ Schwab tables created successfully!")

if __name__ == "__main__":
    create_schwab_tables()