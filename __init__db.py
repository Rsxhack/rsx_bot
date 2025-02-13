import sqlite3

# Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect("transactions.db")
cursor = conn.cursor()

# Create transactions table
cursor.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    username TEXT,
    exchange TEXT,
    amount REAL,
    status TEXT DEFAULT 'Pending'
)
''')

# Insert sample data (optional)
cursor.execute("INSERT INTO transactions (user_id, username, exchange, amount) VALUES ('12345', '@testuser', 'Binance', 1000)")
cursor.execute("INSERT INTO transactions (user_id, username, exchange, amount) VALUES ('67890', '@cryptoKing', 'Bybit', 500)")

# Save and close
conn.commit()
conn.close()

print("✅ Database Initialized Successfully!")
