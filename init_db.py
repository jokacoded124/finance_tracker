"""
Run this file once to create the database and its tables:

    python init_db.py

It is safe to run multiple times - existing tables are left untouched.
"""

import sqlite3

DATABASE = "finance.db"

connection = sqlite3.connect(DATABASE)

connection.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        amount REAL NOT NULL,
        type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
        category TEXT NOT NULL,
        description TEXT,
        payment_method TEXT,
        date TEXT NOT NULL
    )
""")

connection.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        month TEXT NOT NULL UNIQUE,
        amount REAL NOT NULL
    )
""")

connection.commit()
connection.close()

print("Database initialized successfully (finance.db)")
