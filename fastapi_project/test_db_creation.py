#!/usr/bin/env python3
"""
Test script to check database table creation
"""
import sys
sys.path.append('.')

from app.database import Base, engine
from app import models

def main():
    print("Testing database table creation...")
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully!")
        
        # List all tables
        print("\nTables created:")
        for table_name in Base.metadata.tables.keys():
            print(f"  - {table_name}")
            
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
