import sqlite3

conn = sqlite3.connect('test.db')
cursor = conn.cursor()

# Check row counts for position-related tables
tables = ['schwab_positions', 'positions', 'position_snapshots']
for table in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"{table}: {count} rows")

# Get sample data from schwab_positions
print("\nSample from schwab_positions:")
cursor.execute("SELECT * FROM schwab_positions LIMIT 3")
rows = cursor.fetchall()
cursor.execute("PRAGMA table_info(schwab_positions)")
columns = [col[1] for col in cursor.fetchall()]
print(f"Columns: {columns}")
for row in rows:
    print(f"  {dict(zip(columns, row))}")

conn.close()
