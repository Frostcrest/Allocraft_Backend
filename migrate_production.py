#!/usr/bin/env python3
"""
Production Migration Script for Allocraft Backend

This script ensures all database tables exist for production deployment.
It can be run safely multiple times - it only creates missing tables.

Usage:
    python migrate_production.py

Environment Variables:
    DATABASE_URL: Connection string for the database (defaults to SQLite)
"""

import os
import sys
from pathlib import Path

# Add the fastapi_project directory to the Python path
current_dir = Path(__file__).parent
fastapi_dir = current_dir / "fastapi_project"
sys.path.insert(0, str(fastapi_dir))

try:
    from app.database import engine, Base
    from app import models  # This imports all existing models
    from app.models import schwab_models  # This imports the new Schwab models
    
    def create_all_tables():
        """Create all database tables if they don't exist."""
        print("🗄️  Creating database tables...")
        print(f"📍 Database URL: {os.getenv('DATABASE_URL', 'sqlite:///./test.db')}")
        
        try:
            # This will create all tables defined in Base.metadata
            Base.metadata.create_all(bind=engine)
            print("✅ All database tables created successfully!")
            
            # List all tables that were created/verified
            inspector = None
            try:
                from sqlalchemy import inspect
                inspector = inspect(engine)
                table_names = inspector.get_table_names()
                print(f"📋 Database contains {len(table_names)} tables:")
                for table_name in sorted(table_names):
                    print(f"   • {table_name}")
            except ImportError:
                print("   (Table listing unavailable - sqlalchemy inspect not available)")
            except Exception as e:
                print(f"   (Could not list tables: {e})")
                
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            return False
            
        return True
    
    def main():
        """Main migration function."""
        print("🚀 Starting Allocraft Production Migration")
        print("=" * 50)
        
        if create_all_tables():
            print("\n🎉 Migration completed successfully!")
            print("   Your database is ready for production.")
        else:
            print("\n💥 Migration failed!")
            print("   Please check the error messages above.")
            sys.exit(1)
    
    if __name__ == "__main__":
        main()
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the Allocraft_Backend directory")
    print("and that all required packages are installed.")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)
