import sqlite3
from datetime import datetime

def migrate_wheel_cycles_table():
    """Add missing columns to wheel_cycles table"""
    
    conn = sqlite3.connect('test.db')
    cursor = conn.cursor()
    
    try:
        # Check if status_metadata column exists
        cursor.execute("PRAGMA table_info(wheel_cycles);")
        columns = [column[1] for column in cursor.fetchall()]
        
        print(f"Current columns: {columns}")
        
        # Add status_metadata column if it doesn't exist
        if 'status_metadata' not in columns:
            print("Adding status_metadata column...")
            cursor.execute("ALTER TABLE wheel_cycles ADD COLUMN status_metadata TEXT;")
            print("✓ Added status_metadata column")
        else:
            print("✓ status_metadata column already exists")
            
        # Add last_status_update column if it doesn't exist
        if 'last_status_update' not in columns:
            print("Adding last_status_update column...")
            cursor.execute("ALTER TABLE wheel_cycles ADD COLUMN last_status_update DATETIME;")
            print("✓ Added last_status_update column")
            
            # Set default value for existing records
            default_timestamp = datetime.utcnow().isoformat()
            cursor.execute("UPDATE wheel_cycles SET last_status_update = ? WHERE last_status_update IS NULL;", (default_timestamp,))
            print("✓ Set default timestamps for existing records")
        else:
            print("✓ last_status_update column already exists")
        
        conn.commit()
        print("\nMigration completed successfully!")
        
        # Verify the new schema
        cursor.execute("PRAGMA table_info(wheel_cycles);")
        updated_columns = cursor.fetchall()
        print("\nUpdated table schema:")
        for column in updated_columns:
            print(f"  {column[1]} ({column[2]}) - {'NOT NULL' if column[3] else 'NULL'}")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_wheel_cycles_table()
