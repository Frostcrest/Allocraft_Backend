import sqlite3

conn = sqlite3.connect('test.db')
cursor = conn.cursor()

# Get schema for wheel_cycles table
cursor.execute("PRAGMA table_info(wheel_cycles);")
columns = cursor.fetchall()

print('Columns in wheel_cycles table:')
for column in columns:
    print(f"  {column[1]} ({column[2]}) - {'NOT NULL' if column[3] else 'NULL'}")

conn.close()
