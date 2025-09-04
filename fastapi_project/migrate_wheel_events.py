#!/usr/bin/env python3
"""
Migration script to update wheel_events table structure
Adds the columns needed by the dashboard: cycle_id, event_type, contracts, strike, etc.
"""
import sqlite3
from datetime import datetime

def migrate_wheel_events():
    conn = sqlite3.connect('test.db')
    cursor = conn.cursor()
    
    print("=== Migrating wheel_events table ===")
    
    try:
        # First, check current structure
        cursor.execute("PRAGMA table_info(wheel_events)")
        current_columns = {row[1] for row in cursor.fetchall()}
        print(f"Current columns: {current_columns}")
        
        # Add missing columns one by one
        columns_to_add = [
            ('cycle_id', 'INTEGER'),
            ('event_type', 'VARCHAR'),
            ('event_date', 'DATE'),
            ('contracts', 'REAL'),
            ('strike', 'REAL'),
            ('premium', 'REAL'),
            ('notes', 'TEXT')
        ]
        
        for column_name, column_type in columns_to_add:
            if column_name not in current_columns:
                try:
                    cursor.execute(f"ALTER TABLE wheel_events ADD COLUMN {column_name} {column_type}")
                    print(f"✓ Added column: {column_name} ({column_type})")
                except sqlite3.Error as e:
                    print(f"✗ Failed to add column {column_name}: {e}")
        
        # Commit changes
        conn.commit()
        print("Migration completed successfully!")
        
        # Verify final structure
        cursor.execute("PRAGMA table_info(wheel_events)")
        final_columns = [row[1] for row in cursor.fetchall()]
        print(f"Final columns: {final_columns}")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_wheel_events()
