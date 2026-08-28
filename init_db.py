import sqlite3

DATABASE = "finance.db"

connection = sqlite3.connect(DATABASE)

connection.execute("""
CREATE TABLE IF NOT EXISTS budgets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT UNIQUE NOT NULL,
    amount REAL NOT NULL
)
""")

connection.commit()
connection.close()

print("Budget table created successfully!")