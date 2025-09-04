#!/usr/bin/env python3
import sqlite3

# Connect to the database
conn = sqlite3.connect('test.db')
cursor = conn.cursor()

print("=== wheel_events table schema ===")
cursor.execute("PRAGMA table_info(wheel_events)")
for row in cursor.fetchall():
    print(f"Column {row[1]} ({row[2]}) - Primary Key: {row[5]}")

print("\n=== Sample wheel_events data ===")
cursor.execute("SELECT * FROM wheel_events LIMIT 5")
columns = [description[0] for description in cursor.description]
print("Columns:", columns)
for row in cursor.fetchall():
    print(row)

conn.close()
