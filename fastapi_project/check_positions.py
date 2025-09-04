#!/usr/bin/env python3
import sqlite3

# Connect to the database
conn = sqlite3.connect('test.db')
cursor = conn.cursor()

print("=== Checking positions table ===")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%position%'")
tables = cursor.fetchall()
print("Position-related tables:", [t[0] for t in tables])

for table_name in [t[0] for t in tables]:
    print(f"\n=== {table_name} table ===")
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    print(f"Columns: {[col[1] for col in columns]}")
    
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"Row count: {count}")
    
    if count > 0:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        sample_data = cursor.fetchall()
        print("Sample data:")
        for i, row in enumerate(sample_data):
            print(f"  Row {i+1}: {row}")

print("\n=== Checking other position sources ===")
for table in ['stocks', 'options', 'schwab_positions']:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{table}: {count} rows")
        
        if count > 0:
            cursor.execute(f"SELECT * FROM {table} LIMIT 2")
            sample = cursor.fetchall()
            print(f"  Sample from {table}: {sample}")
    except Exception as e:
        print(f"{table}: Error - {e}")

conn.close()
